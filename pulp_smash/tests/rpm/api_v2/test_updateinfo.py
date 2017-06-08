# coding=utf-8
"""Test the ``updateinfo.xml`` files published by Pulp's yum distributor.

The purpose of an ``updateinfo.xml`` file is to document the errata (i.e.
maintenance patches) provided by a repository. For an overview of the structure
and contents of such a file, see `openSUSE:Standards Rpm Metadata UpdateInfo`_.
Beware that yum and dnf do not adhere to the openSUSE standards. We link to
their standard anyway because it's easier to understand than yum or dnf's
source code. (!)

One discrepancy is in the schema for the ``<pkglist>`` element. According to
the yum source code, it has the following structure:

.. code-block:: xml

    <!ELEMENT pkglist (collection+)>
    <!ELEMENT collection (name?, package+)>
        <!ATTLIST collection short CDATA #IMPLIED>
        <!ATTLIST collection name CDATA #IMPLIED>
    <!ELEMENT name (#PCDATA)>

Here's a concrete example of what that might look like:

.. code-block:: xml

    <pkglist>
        <collection name="…" short="…">
            <name>…</name>
            <package>…</package>
            <package>…</package>
        </collection>
    </pkglist>

yum (and, therefore, dnf) allows a ``<collection>`` element to have "name" and
"short" attributes. openSUSE does not.

.. _openSUSE:Standards Rpm Metadata UpdateInfo:
    https://en.opensuse.org/openSUSE:Standards_Rpm_Metadata_UpdateInfo
"""
import unittest
from urllib.parse import urljoin
from xml.etree import ElementTree

from packaging.version import Version
from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_ERRATUM_ID,
    RPM_ERRATUM_RPM_NAME,
    RPM_NAMESPACES,
    RPM_PKGLISTS_UPDATEINFO_FEED_URL,
    RPM_SIGNED_FEED_URL,
    RPM_UNSIGNED_FEED_URL,
    RPM_UNSIGNED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata,
    get_repodata_repomd_xml,
)
from pulp_smash.tests.rpm.utils import (
    check_issue_2277,
    check_issue_2620,
    set_up_module,
)


def setUpModule():  # pylint:disable=invalid-name
    """Possibly skip the tests in this module.

    Skip tests if `Pulp #2277 <https://pulp.plan.io/issues/2277>`_ affects us.
    """
    set_up_module()
    cfg = config.get_config()
    if cfg.version < Version('2.11') and check_issue_2277(cfg):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2277')


def _gen_errata():
    """Generate and return a typical erratum with a unique ID."""
    return {
        'id': utils.uuid4(),
        'description': (
            'This sample description contains some non-ASCII characters '
            ', such as: 汉堡™, and also contains a long line which some '
            'systems may be tempted to wrap.  It will be tested to see '
            'if the string survives a round-trip through the API and '
            'back out of the yum distributor as XML without any '
            'modification.'
        ),
        'issued': '2015-03-05 05:42:53 UTC',
        'pkglist': [{
            'name': 'pkglist-name',
            # This package is present in Pulp Fixtures.
            'packages': [{
                'arch': 'noarch',
                'epoch': '0',
                'filename': 'bear-4.1-1.noarch.rpm',
                'name': 'bear',
                'release': '1',
                'sum': [
                    'sha256',
                    ('ceb0f0bb58be244393cc565e8ee5ef0ad36884d8ba8eec74542ff47'
                     'd299a34c1')
                ],
                'version': '4.1',
            }],
        }],
        'references': [{
            'href': 'https://example.com/errata/PULP-2017-1234.html',
            'id': 'PULP-2017:1234',
            'title': 'PULP-2017:1234',
            'type': 'self'
        }],
        'solution': 'sample solution',
        'status': 'final',
        'title': 'sample title',
        'type': 'pulp',
        'version': '6',  # intentionally string, not int
    }


def _get_updates_by_id(update_info_tree):
    """Return each "update" element in ``update_info_tree``, keyed by ID.

    :param update_info_tree: An ``Element``.
    :returns: A dict in the form ``{id, update_element}``.
    """
    return {
        update.findall('id')[0].text: update
        for update in update_info_tree.findall('update')
    }


class UpdateInfoTestCase(utils.BaseAPITestCase):
    """Tests to ensure ``updateinfo.xml`` can be created and is valid."""

    @classmethod
    def setUpClass(cls):
        """Create, populate and publish a repository.

        More specifically, do the following:

        1. Create an RPM repository with a distributor.
        2. Populate the repository with an RPM and two errata, where one
           erratum references the RPM, and the other does not.
        3. Publish the repository Fetch and parse its ``updateinfo.xml`` file.
        """
        super(UpdateInfoTestCase, cls).setUpClass()
        cls.errata = {key: _gen_errata() for key in ('full', 'partial')}
        del cls.errata['partial']['pkglist']
        cls.tasks = {}

        # Create a repo.
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        try:
            # Populate and publish the repo.
            repo = client.get(repo['_href'], params={'details': True})
            unit = utils.http_get(RPM_UNSIGNED_URL)
            utils.upload_import_unit(
                cls.cfg, unit, {'unit_type_id': 'rpm'}, repo
            )
            for key, erratum in cls.errata.items():
                report = utils.upload_import_erratum(
                    cls.cfg, erratum, repo['_href']
                )
                cls.tasks[key] = tuple(api.poll_spawned_tasks(cls.cfg, report))
            utils.publish_repo(cls.cfg, repo)

            # Fetch and parse updateinfo.xml.
            cls.updates_element = (
                get_repodata(cls.cfg, repo['distributors'][0], 'updateinfo')
            )
        except:
            cls.tearDownClass()
            raise

    def test_one_task_per_import(self):
        """Assert only one task is spawned per erratum upload."""
        for key, tasks in self.tasks.items():
            with self.subTest(key=key):
                self.assertEqual(len(tasks), 1)

    def test_tasks_state(self):
        """Assert each task's state is "finished".

        This test assumes :meth:`test_one_task_per_import` passes.
        """
        for key, tasks in self.tasks.items():
            with self.subTest(key=key):
                self.assertEqual(tasks[0]['state'], 'finished')

    def test_tasks_result(self):
        """Assert each task's result success flag (if present) is true.

        This test assumes :meth:`test_one_task_per_import` passes.
        """
        for key, tasks in self.tasks.items():
            with self.subTest(key=key):
                if 'result' not in tasks[0]:
                    continue
                result = tasks[0]['result']
                self.assertTrue(result['success_flag'], result)

    def test_updates_element(self):
        """Assert ``updateinfo.xml`` has a root element named ``updates``."""
        self.assertEqual(self.updates_element.tag, 'updates')

    def test_update_elements(self):
        """Assert there is one "update" element in ``updateinfo.xml``."""
        self.assertEqual(len(self.updates_element.findall('update')), 1)

    def test_reboot_not_suggested(self):
        """Assert the update info tree does not suggest a spurious reboot.

        The errata uploaded by this test case do not suggest that a reboot be
        applied. As a result, the relevant ``<update>`` element in the
        ``updateinfo.xml`` file should not have a ``<reboot_suggested>`` tag.
        Verify that this is so. See `Pulp #2032`_.

        .. NOTE:: In previous versions of Pulp, if no reboot should be applied,
            a ``<reboot_suggested>False</reboot_suggested>`` element would be
            present. See `Pulp #1782`_.

        .. _Pulp #1782: https://pulp.plan.io/issues/1782
        .. _Pulp #2032: https://pulp.plan.io/issues/2032
        """
        if selectors.bug_is_untestable(2032, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2032')
        erratum = self.errata['full']
        update_element = (
            _get_updates_by_id(self.updates_element)[erratum['id']]
        )
        reboot_elements = update_element.findall('reboot_suggested')
        self.assertEqual(len(reboot_elements), 0)

    def test_erratum(self):
        """Assert the erratum generated by Pulp is correct.

        Walk through each top-level element of the erratum which was generated
        during this test case's set-up and uploaded to Pulp. For each element,
        verify that the ``updateinfo.xml`` file generated by Pulp has a
        corresponding entry. Each of the ``verify_*`` methods on this test case
        implement the test logic for a single element.
        """
        # If a new top-level element is added to `erratum` and no corresponding
        # verify_* method is added here, then an exception will be raised when
        # getattr() executes. This is intentional: it ensures we have tests for
        # all top-level elements.
        erratum = self.errata['full']
        update_element = (
            _get_updates_by_id(self.updates_element)[erratum['id']]
        )
        for key in erratum.keys():
            with self.subTest(key=key):
                getattr(self, 'verify_{}'.format(key))(erratum, update_element)

    def verify_id(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same id."""
        id_element = update_element.find('id')
        self.assertEqual(erratum['id'], id_element.text)

    def verify_description(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have same description."""
        description_element = update_element.find('description')
        self.assertEqual(erratum['description'], description_element.text)

    def verify_issued(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same issued."""
        issued_element = update_element.find('issued')
        self.assertEqual(erratum['issued'], issued_element.get('date'))

    def verify_pkglist(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same pkglist."""
        package_elements = update_element.findall('pkglist/collection/package')
        self.assertEqual(len(package_elements), 1)

        package = erratum['pkglist'][0]['packages'][0]
        package_element = package_elements[0]
        for key in ('arch', 'epoch', 'name', 'release', 'version'):
            self.assertEqual(package[key], package_element.get(key))
        self.assertEqual(
            package['filename'],
            package_element.find('filename').text
        )
        self.assertEqual(
            package['sum'][0],
            package_element.find('sum').get('type')
        )
        self.assertEqual(package['sum'][1], package_element.find('sum').text)

    def verify_references(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have same references."""
        reference_elements = update_element.findall('references/reference')
        self.assertEqual(len(reference_elements), 1)

        reference_element = reference_elements[0]
        self.assertEqual(reference_element.attrib, erratum['references'][0])

    def verify_solution(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same solution."""
        solution_element = update_element.find('solution')
        self.assertEqual(erratum['solution'], solution_element.text)

    def verify_status(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same status."""
        self.assertEqual(erratum['status'], update_element.get('status'))

    def verify_title(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same title."""
        title_element = update_element.find('title')
        self.assertEqual(erratum['title'], title_element.text)

    def verify_type(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same type."""
        self.assertEqual(erratum['type'], update_element.get('type'))

    def verify_version(self, erratum, update_element):
        """Verify ``erratum`` and ``update_element`` have the same version."""
        self.assertEqual(erratum['version'], update_element.get('version'))


class UpdateRepoTestCase(utils.BaseAPITestCase):
    """Verify ``updateinfo.xml`` changes as its repo changes."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a feed and distributor."""
        super().setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        try:
            repo = client.post(REPOSITORY_PATH, body)
            cls.resources.add(repo['_href'])
            cls.repo = client.get(repo['_href'], params={'details': True})
        except:
            cls.tearDownClass()
            raise

    def test_01_sync_publish(self):
        """Sync and publish the repository.

        When executed, this test method will fetch ``updateinfo.xml`` and
        verify that:

        * An ``<update>`` with an ``<id>`` of
          :data:`pulp_smash.constants.RPM_ERRATUM_ID` is present, and
        * one of its child ``<package>`` elements has a "name" attribute equal
          to :data:`pulp_smash.constants.RPM_ERRATUM_RPM_NAME`.
        """
        utils.sync_repo(self.cfg, self.repo)
        utils.publish_repo(self.cfg, self.repo)
        updates_element = (
            get_repodata(self.cfg, self.repo['distributors'][0], 'updateinfo')
        )
        update_elements = _get_updates_by_id(updates_element)
        self.assertIn(RPM_ERRATUM_ID, update_elements)

        package_elements = (
            update_elements[RPM_ERRATUM_ID]
            .findall('pkglist/collection/package'))
        package_names = [
            package_element.get('name') for package_element in package_elements
        ]
        self.assertIn(RPM_ERRATUM_RPM_NAME, package_names)

    def test_02_unassociate_publish(self):
        """Unassociate a content unit and publish the repository.

        Fetch ``updateinfo.xml``. Verify that an ``<update>`` with an ``<id>``
        of :data:`pulp_smash.constants.RPM_ERRATUM_ID` is not present.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.post(urljoin(self.repo['_href'], 'actions/unassociate/'), {
            'criteria': {'filters': {'unit': {'name': RPM_ERRATUM_RPM_NAME}}}
        })
        utils.publish_repo(self.cfg, self.repo)
        updates_element = (
            get_repodata(self.cfg, self.repo['distributors'][0], 'updateinfo')
        )
        update_elements = _get_updates_by_id(updates_element)
        self.assertNotIn(RPM_ERRATUM_ID, update_elements)


class PkglistsTestCase(unittest.TestCase):
    """Sync a repository whose updateinfo file has multiple pkglist sections.

    This test case targets `Pulp #2227 <https://pulp.plan.io/issues/2227>`_.
    """

    def test_all(self):
        """Sync a repo whose updateinfo file has multiple pkglist sections.

        Specifically, do the following:

        1. Create, sync and publish an RPM repository whose feed is set to
           :data:`pulp_smash.constants.RPM_PKGLISTS_UPDATEINFO_FEED_URL`.
        2. Fetch and parse the published repository's ``updateinfo.xml`` file.

        Verify that the ``updateinfo.xml`` file has three packages whose
        ``<filename>`` elements have the following text:

        * penguin-0.9.1-1.noarch.rpm
        * shark-0.1-1.noarch.rpm
        * walrus-5.21-1.noarch.rpm

        Note that Pulp is free to change the structure of a source repository
        at will. For example, the source repository has three ``<collection>``
        elements, the published repository can have one, two or three
        ``<collection>`` elements. Assertions are not made about these details.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(2227, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2277')

        # Create, sync and publish a repository.
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_PKGLISTS_UPDATEINFO_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo)

        # Fetch and parse ``updateinfo.xml``.
        updates_element = (
            get_repodata(cfg, repo['distributors'][0], 'updateinfo')
        )

        # Verify the ``updateinfo.xml`` file.
        debug = ElementTree.tostring(updates_element)
        filename_elements = (
            updates_element
            .findall('update/pkglist/collection/package/filename'))
        filenames = [
            filename_element.text for filename_element in filename_elements
        ]
        filenames.sort()
        self.assertEqual(filenames, [
            'penguin-0.9.1-1.noarch.rpm',
            'shark-0.1-1.noarch.rpm',
            'walrus-5.21-1.noarch.rpm',
        ], debug)


class CleanUpTestCase(unittest.TestCase):
    """Test whether old ``updateinfo.xml`` files are cleaned up.

    Do the following:

    1. Create, populate and publish a repository. Verify that an
       ``updateinfo.xml`` file is present and can be downloaded.
    2. Add an additional content unit to the repository, and publish it again.
       Verify that the ``updateinfo.xml`` file created by the first publish is
       no longer available, and that a new ``updateinfo.xml`` file is
       available.

    This procedure targets `Pulp #2096 <https://pulp.plan.io/issues/2096>`_.
    Note that the second publish must be an incremental publish.
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository."""
        cls.cfg = config.get_config()
        if check_issue_2620(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        cls.repo = client.post(REPOSITORY_PATH, body)
        try:
            cls.repo = client.get(cls.repo['_href'], params={'details': True})
        except:
            cls.tearDownClass()
            raise
        cls.updateinfo_xml_hrefs = []

    @classmethod
    def tearDownClass(cls):
        """Remove the created repository and any orphans."""
        client = api.Client(cls.cfg)
        client.delete(cls.repo['_href'])
        client.delete(ORPHANS_PATH)

    def test_01_first_publish(self):
        """Populate and publish the repository."""
        utils.sync_repo(self.cfg, self.repo)
        client = api.Client(self.cfg)
        client.post(urljoin(self.repo['_href'], 'actions/unassociate/'), {
            'criteria': {
                'filters': {'unit': {'filename': RPM}},
                'type_ids': ('rpm',),
            }
        })
        utils.publish_repo(self.cfg, self.repo)
        self.updateinfo_xml_hrefs.append(self.get_updateinfo_xml_href())

        with self.subTest(comment='check number of RPMs in repo'):
            units = (
                utils.search_units(self.cfg, self.repo, {'type_ids': ('rpm',)})
            )
            self.assertEqual(len(units), 31)
        with self.subTest(comment='check updateinfo.xml is available'):
            client.get(self.updateinfo_xml_hrefs[0])

    def test_02_second_publish(self):
        """Add an additional content unit and publish the repository again."""
        utils.sync_repo(self.cfg, self.repo)
        utils.publish_repo(self.cfg, self.repo)
        self.updateinfo_xml_hrefs.append(self.get_updateinfo_xml_href())

        client = api.Client(self.cfg)
        with self.subTest(comment='check number of RPMs in repo'):
            units = (
                utils.search_units(self.cfg, self.repo, {'type_ids': ('rpm',)})
            )
            self.assertEqual(len(units), 32)
        with self.subTest(comment='check updateinfo.xml has a new path'):
            # pylint:disable=no-value-for-parameter
            self.assertNotEqual(*self.updateinfo_xml_hrefs)
        with self.subTest(comment='check old updateinfo.xml is unavailable'):
            with self.assertRaises(HTTPError):
                client.get(self.updateinfo_xml_hrefs[0])
        with self.subTest(comment='check new updateinfo.xml is available'):
            client.get(self.updateinfo_xml_hrefs[1])

    def get_updateinfo_xml_href(self):
        """Return the path to the ``updateinfo.xml`` file."""
        # Download and search through ``.../repodata/repomd.xml``.
        distributor = self.repo['distributors'][0]
        repomd_xml = get_repodata_repomd_xml(self.cfg, distributor)
        xpath = (
            "{{{namespace}}}data[@type='updateinfo']/{{{namespace}}}location"
            .format(namespace=RPM_NAMESPACES['metadata/repo'])
        )
        location_elements = repomd_xml.findall(xpath)

        # Build the URL to the updateinfo.xml file.
        path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
        if not path.endswith('/'):
            path += '/'
        path = urljoin(path, location_elements[0].get('href'))
        return path
