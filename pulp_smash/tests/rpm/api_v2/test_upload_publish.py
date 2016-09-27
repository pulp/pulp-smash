# coding=utf-8
"""Tests that upload to and publish RPM repositories.

For information on repository upload and publish operations, see `Uploading
Content`_ and `Publication`_.

.. _Publication:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html
.. _Uploading Content:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html
"""
import unittest
from itertools import product
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.utils import upload_import_unit
from pulp_smash.constants import (
    CALL_REPORT_KEYS,
    CONTENT_UPLOAD_PATH,
    DRPM,
    DRPM_UNSIGNED_URL,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
    RPM_URL,
    SRPM,
    SRPM_UNSIGNED_URL,
)
from pulp_smash.tests.rpm.utils import gen_erratum
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repomd_xml,
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def parse_updateinfo_update(update):
    """Create an erratum from an ``updateinfo.xml`` update.

    This function creates an empty erratum, then parses a top-level ``update``
    section from an ``updateinfo.xml`` file, and populates the empty erratum
    from such.

    .. WARNING:: There is no schema for ``updateinfo.xml`` files. Instead, this
        function's parsing logic is reverse-engineered from the DNF source
        code. As a result, this function may exhibit erroneous behaviour.

        As of this writing, the DNF source code can be cloned from
        ``https://github.com/rpm-software-management/dnf.git``. The files used
        by this function are:

        * `dnf/cli/commands/updateinfo.py`_
        * `tests/repos/rpm/updateinfo.xml`_

    .. NOTE:: DNF is incompatible with the openSUSE ``updateinfo.xml`` schema.
        The schema can be found from the `openSUSE:Standards Rpm Metadata
        UpdateInfo`_ wiki page.

    :param update: An ``xml.etree`` element corresponding to an "update"
        element in an ``updateinfo.xml`` file.
    :returns: An erratum. In other words, a dict with keys like "description,"
        "from," and "id."

    .. _dnf/cli/commands/updateinfo.py:
        https://github.com/rpm-software-management/dnf/blob/master/dnf/cli/commands/updateinfo.py
    .. _tests/repos/rpm/updateinfo.xml:
        https://github.com/rpm-software-management/dnf/blob/master/tests/repos/rpm/updateinfo.xml
    .. _openSUSE:Standards Rpm Metadata UpdateInfo:
        https://en.opensuse.org/openSUSE:Standards_Rpm_Metadata_UpdateInfo
    """
    erratum = {
        'pkglist': _get_pkglist(update),
        'reboot_suggested': _get_reboot_suggested(update),
        'references': _get_references(update),
    }
    for key in ('from', 'status', 'type', 'version'):
        erratum[key] = update.attrib[key]
    for key in ('issued', 'updated'):
        erratum[key] = update.find(key).attrib['date']
    for key in (
            'description',
            'id',
            'pushcount',
            'rights',
            'severity',
            'solution',
            'summary',
            'title',):
        erratum[key] = update.find(key).text
    return erratum


def _get_reboot_suggested(update):
    """Tell whether an ``updateinfo.xml`` update suggests a reboot.

    :param update: An ``xml.etree`` element corresponding to an "update"
        element in an ``updateinfo.xml`` file.
    :returns: ``True`` or ``False`` if the update has a ``reboot_suggested``
        element with a value of ``'True'`` or ``'False'``, respectively;
        ``False`` if no ``reboot_suggested`` element is present; or an error
        otherwise.
    """
    reboot_suggested = update.find('reboot_suggested')
    if reboot_suggested is None:
        return False
    legend = {'True': True, 'False': False}
    return legend[reboot_suggested.text]


def _get_references(update):
    """Parse the "references" element in an ``updateinfo.xml`` update.

    :param update: An ``xml.etree`` element corresponding to an "update"
        element in an ``updateinfo.xml`` file.
    :returns: A list of references, each in the format used by an erratum.
    """
    return [
        {key: reference.attrib[key] for key in ('href', 'id', 'title', 'type')}
        for reference in update.find('references').findall('reference')
    ]


def _get_pkglist(update):
    """Parse the "pkglist" element in an ``updateinfo.xml`` update.

    :param update: An ``xml.etree`` element corresponding to an "update"
        element in an ``updateinfo.xml`` file.
    :returns: A list of packages, each in the format used by an erratum.
    """
    src_pkglist = update.find('pkglist')
    out_pkglist = [{
        'name': src_pkglist.find('collection').find('name').text,
        'packages': [],
        'short': src_pkglist.find('collection').attrib['short'],
    }]
    for package in src_pkglist.find('collection').findall('package'):
        out_pkglist[0]['packages'].append({
            'arch': package.attrib['arch'],
            'epoch': package.attrib['epoch'],
            'filename': package.find('filename').text,
            'name': package.attrib['name'],
            'release': package.attrib['release'],
            'src': package.attrib['src'],
            'version': package.attrib['version'],
        })
        if selectors.bug_is_testable(2042, config.get_config().version):
            checksum = package.find('sum')
            out_pkglist[0]['packages'][-1]['sum'] = [
                checksum.attrib['type'], checksum.text
            ]
    return out_pkglist


class UploadDrpmTestCase(utils.BaseAPITestCase):
    """Test whether one can upload a DRPM into a repository.

    This test case targets `Pulp Smash #336
    <https://github.com/PulpQE/pulp-smash/issues/336>`_
    """

    @classmethod
    def setUpClass(cls):
        """Import a DRPM into a repository and search it for content units.

        Specifically, this method does the following:

        1. Create a yum repository.
        2. Upload a DRPM into the repository.
        3. Search for all content units in the repository.
        """
        super(UploadDrpmTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1806, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1806')
        client = api.Client(cls.cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        cls.resources.add(repo['_href'])
        drpm = utils.http_get(DRPM_UNSIGNED_URL)
        upload_import_unit(cls.cfg, drpm, 'drpm', repo['_href'])
        cls.repo_units = client.post(
            urljoin(repo['_href'], 'search/units/'),
            {'criteria': {}},
        )

    def test_status_code_repo_units(self):
        """Verify the HTTP status code for repo units response."""
        self.assertEqual(self.repo_units.status_code, 200)

    def test_drpm_uploaded_successfully(self):
        """Test if DRPM has been uploaded successfully."""
        self.assertEqual(len(self.repo_units.json()), 1)

    def test_drpm_file_name_is_correct(self):
        """Test if DRPM extracted correct metadata for creating filename."""
        self.assertEqual(
            self.repo_units.json()[0]['metadata']['filename'],
            DRPM,
        )


class UploadSrpmTestCase(utils.BaseAPITestCase):
    """Test whether one can upload a SRPM into a repository.

    This test case targets `Pulp Smash #402
    <https://github.com/PulpQE/pulp-smash/issues/402>`_
    """

    @classmethod
    def setUpClass(cls):
        """Import a SRPM into a repository and search it for content units.

        Specifically, this method does the following:

        1. Create a yum repository.
        2. Upload a SRPM into the repository.
        3. Search for all content units in the repository.
        """
        super(UploadSrpmTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        cls.resources.add(repo['_href'])
        srpm = utils.http_get(SRPM_UNSIGNED_URL)
        upload_import_unit(cls.cfg, srpm, 'srpm', repo['_href'])
        cls.repo_units = client.post(
            urljoin(repo['_href'], 'search/units/'),
            {'criteria': {}},
        )

    def test_status_code_repo_units(self):
        """Verify the HTTP status code for repo units response."""
        self.assertEqual(self.repo_units.status_code, 200)

    def test_srpm_uploaded_successfully(self):
        """Test if SRPM has been uploaded successfully."""
        self.assertEqual(len(self.repo_units.json()), 1)

    def test_srpm_file_name_is_correct(self):
        """Test if SRPM extracted correct metadata for creating filename."""
        self.assertEqual(
            self.repo_units.json()[0]['metadata']['filename'],
            SRPM,
        )


class UploadRpmTestCase(utils.BaseAPITestCase):
    """Test whether one can upload, associate and publish RPMs."""

    @classmethod
    def setUpClass(cls):
        """Upload an RPM to a repo, copy it to another, publish and download.

        Do the following:

        1. Create two RPM repositories, both without feeds.
        2. Upload an RPM to the first repository.
        3. Associate the first repository with the second, causing the RPM to
           be copied.
        4. Add a distributor to both repositories and publish them.
        """
        super(UploadRpmTestCase, cls).setUpClass()
        utils.reset_pulp(cls.cfg)  # See: https://pulp.plan.io/issues/1406
        cls.responses = {}

        # Download an RPM and create two repositories.
        client = api.Client(cls.cfg, api.json_handler)
        repos = [client.post(REPOSITORY_PATH, gen_repo()) for _ in range(2)]
        for repo in repos:
            cls.resources.add(repo['_href'])
        client.response_handler = api.safe_handler
        cls.rpm = utils.http_get(RPM_URL)

        # Begin an upload request, upload an RPM, move the RPM into a
        # repository, and end the upload request.
        cls.responses['malloc'] = client.post(CONTENT_UPLOAD_PATH)
        cls.responses['upload'] = client.put(
            urljoin(cls.responses['malloc'].json()['_href'], '0/'),
            data=cls.rpm,
        )
        cls.responses['import'] = client.post(
            urljoin(repos[0]['_href'], 'actions/import_upload/'),
            {
                'unit_key': {},
                'unit_type_id': 'rpm',
                'upload_id': cls.responses['malloc'].json()['upload_id'],
            },
        )
        cls.responses['free'] = client.delete(
            cls.responses['malloc'].json()['_href'],
        )

        # Copy content from the first repository to the second.
        cls.responses['copy'] = client.post(
            urljoin(repos[1]['_href'], 'actions/associate/'),
            {'source_repo_id': repos[0]['id']}
        )

        # Add a distributor to and publish both repositories.
        cls.responses['distribute'] = []
        cls.responses['publish'] = []
        for repo in repos:
            cls.responses['distribute'].append(client.post(
                urljoin(repo['_href'], 'distributors/'),
                gen_distributor(),
            ))
            cls.responses['publish'].append(client.post(
                urljoin(repo['_href'], 'actions/publish/'),
                {'id': cls.responses['distribute'][-1].json()['id']},
            ))

        # Search for all units in each of the two repositories.
        body = {'criteria': {}}
        cls.responses['repo units'] = [
            client.post(urljoin(repo['_href'], 'search/units/'), body)
            for repo in repos
        ]

    def test_status_code(self):
        """Verify the HTTP status code of each server response."""
        for step, code in (
                ('malloc', 201),
                ('upload', 200),
                ('import', 202),
                ('free', 200),
                ('copy', 202),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)
        for step, code in (
                ('distribute', 201),
                ('publish', 202),
                ('repo units', 200),
        ):
            with self.subTest(step=step):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_malloc(self):
        """Verify the response body for `creating an upload request`_.

        .. _creating an upload request:
           http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#creating-an-upload-request
        """
        keys = set(self.responses['malloc'].json().keys())
        self.assertLessEqual({'_href', 'upload_id'}, keys)

    def test_upload(self):
        """Verify the response body for `uploading bits`_.

        .. _uploading bits:
           http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#upload-bits
        """
        self.assertIsNone(self.responses['upload'].json())

    def test_call_report_keys(self):
        """Verify each call report has a sane structure.

        * `Import into a Repository
          <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#import-into-a-repository>`_
        * `Copying Units Between Repositories
          <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/associate.html#copying-units-between-repositories>`_
        """
        for step in {'import', 'copy'}:
            with self.subTest(step=step):
                keys = frozenset(self.responses[step].json().keys())
                self.assertLessEqual(CALL_REPORT_KEYS, keys)

    def test_call_report_errors(self):
        """Verify each call report is error-free."""
        for step, key in product({'import', 'copy'}, {'error', 'result'}):
            with self.subTest((step, key)):
                self.assertIsNone(self.responses[step].json()[key])

    def test_free(self):
        """Verify the response body for ending an upload.

        `Delete an Upload Request
        <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#delete-an-upload-request>`_
        """
        self.assertIsNone(self.responses['free'].json())

    def test_publish_keys(self):
        """Verify publishing a repository generates a call report."""
        for i, response in enumerate(self.responses['publish']):
            with self.subTest(i=i):
                keys = frozenset(response.json().keys())
                self.assertLessEqual(CALL_REPORT_KEYS, keys)

    def test_publish_errors(self):
        """Verify publishing a call report doesn't generate any errors."""
        for i, response in enumerate(self.responses['publish']):
            for key in {'error', 'result'}:
                with self.subTest((i, key)):
                    self.assertIsNone(response.json()[key])

    def test_repo_units_consistency(self):
        """Verify the two repositories have the same content units."""
        bodies = [resp.json() for resp in self.responses['repo units']]
        self.assertEqual(
            set(unit['unit_id'] for unit in bodies[0]),  # This test is fragile
            set(unit['unit_id'] for unit in bodies[1]),  # due to hard-coded
        )  # indices. But the data is complex, and this makes things simpler.

    def test_unit_integrity(self):
        """Download and verify an RPM from each Pulp distributor."""
        if selectors.bug_is_untestable(2277, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2277')
        for response in self.responses['distribute']:
            distributor = response.json()
            with self.subTest(distributor=distributor):
                url = urljoin(
                    '/pulp/repos/',
                    response.json()['config']['relative_url']
                )
                url = urljoin(url, RPM)
                rpm = api.Client(self.cfg).get(url).content
                self.assertEqual(rpm, self.rpm)


class UploadErratumTestCase(utils.BaseAPITestCase):
    """Test whether one can upload and publish erratum."""

    @classmethod
    def setUpClass(cls):
        """Upload an erratum to a repo, publish, and download the erratum.

        Do the following:

        1. Create an RPM repository with a distributor.
        2. Upload an erratum to the repository.
        3. Publish the repository.
        4. Fetch the repository's ``updateinfo.xml`` file.
        """
        super(UploadErratumTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(2277, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        cls.erratum = gen_erratum()

        # Create an RPM repository with a feed and distributor.
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Sync content into the repository, and give it an erratum.
        utils.sync_repo(cls.cfg, repo['_href'])
        utils.upload_import_erratum(cls.cfg, cls.erratum, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})

        # Publish the repository, and fetch and parse updateinfo.xml
        distributor = repo['distributors'][0]
        client.post(
            urljoin(repo['_href'], 'actions/publish/'),
            {'id': distributor['id']},
        )
        path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
        cls.updateinfo = get_repomd_xml(cls.cfg, path, 'updateinfo')

    def test_updateinfo_root_tag(self):
        """Assert ``updateinfo.xml`` has a root element named ``updates``."""
        self.assertEqual(self.updateinfo.tag, 'updates')

    def test_updates_are_present(self):
        """Assert at least one update is present in ``updateinfo.xml``."""
        n_updates = len(self.updateinfo.findall('update'))
        self.assertGreater(n_updates, 0)

    def test_update_is_correct(self):
        """Assert the uploaded erratum is in ``updateinfo.xml`` and correct.

        Specificially, this method does the following:

        1. Select the "update" element in ``updateinfo.xml`` corresponding to
           the uploaded erratum.
        2. Build our own erratum from the selected "update" element.
        3. Compare the uploaded erratum to the generated erratum.

        .. WARNING:: This test may be erroneous. See
            :func:`parse_updateinfo_update`.
        """
        # Find our erratum in ``updateinfo.xml``.
        updates = [
            update for update in self.updateinfo.findall('update')
            if update.find('id').text == self.erratum['id']
        ]
        self.assertEqual(len(updates), 1)

        # The erratum we uploaded will be different from the erratum that Pulp
        # published. Here, we try to erase the differences between the two, by
        # modifying the uploaded erratum.
        old_erratum = self.erratum.copy()  # dont modify original
        if selectors.bug_is_untestable(2021, self.cfg.version):
            del old_erratum['release']
        if selectors.bug_is_testable(2042, self.cfg.version):
            for package_list in old_erratum['pkglist']:
                for package in package_list['packages']:
                    # ['md5', '…', 'sha256', '…'] → ['sha256': '…']
                    i = package['sum'].index('sha256')
                    package['sum'] = package['sum'][i:i + 2]
        else:
            for package_list in old_erratum['pkglist']:
                for package in package_list['packages']:
                    del package['sum']
        new_erratum = parse_updateinfo_update(updates[0])

        # Parse and verify the erratum. Simply asserting that the original
        # erratum and constructed erratum are equal produces awful failure
        # messages. Iterating like this lets us narrow things down a bit.
        for key, value in old_erratum.items():
            with self.subTest(key=key):
                self.assertIn(key, new_erratum)
                self.assertEqual(value, new_erratum[key])
