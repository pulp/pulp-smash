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
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    DRPM,
    DRPM_UNSIGNED_URL,
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_UNSIGNED_FEED_URL,
    RPM_UNSIGNED_URL,
    SRPM,
    SRPM_UNSIGNED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata,
    get_unit,
)
from pulp_smash.tests.rpm.utils import (
    check_issue_2277,
    check_issue_2387,
    check_issue_2620,
    gen_erratum,
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
        utils.upload_import_unit(cls.cfg, drpm, {'unit_type_id': 'drpm'}, repo)
        cls.units = utils.search_units(cls.cfg, repo, {}, api.safe_handler)

    def test_status_code_units(self):
        """Verify the HTTP status code for repo units response."""
        self.assertEqual(self.units.status_code, 200)

    def test_drpm_uploaded_successfully(self):
        """Test if DRPM has been uploaded successfully."""
        self.assertEqual(len(self.units.json()), 1)

    def test_drpm_file_name_is_correct(self):
        """Test if DRPM extracted correct metadata for creating filename."""
        self.assertEqual(
            self.units.json()[0]['metadata']['filename'],
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
        if check_issue_2620(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')
        client = api.Client(cls.cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        cls.resources.add(repo['_href'])
        srpm = utils.http_get(SRPM_UNSIGNED_URL)
        utils.upload_import_unit(cls.cfg, srpm, {'unit_type_id': 'srpm'}, repo)
        cls.units = utils.search_units(cls.cfg, repo, {}, api.safe_handler)

    def test_status_code_units(self):
        """Verify the HTTP status code for repo units response."""
        self.assertEqual(self.units.status_code, 200)

    def test_srpm_uploaded_successfully(self):
        """Test if SRPM has been uploaded successfully."""
        self.assertEqual(len(self.units.json()), 1)

    def test_srpm_file_name_is_correct(self):
        """Test if SRPM extracted correct metadata for creating filename."""
        self.assertEqual(
            self.units.json()[0]['metadata']['filename'],
            SRPM,
        )


class UploadRpmTestCase(utils.BaseAPITestCase):
    """Test whether one can upload, associate and publish RPMs.

    The test procedure is as follows:

    1. Create a pair of repositories.
    2. Upload an RPM to the first repository, and publish it.
    3. Copy the RPM to the second repository, and publish it.
    """

    @classmethod
    def setUpClass(cls):
        """Create a pair of RPM repositories."""
        cls.cfg = config.get_config()
        if check_issue_2620(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')
        cls.rpm = utils.http_get(RPM_UNSIGNED_URL)
        client = api.Client(cls.cfg, api.json_handler)
        cls.repos = []
        try:
            for _ in range(2):
                body = gen_repo()
                body['distributors'] = [gen_distributor()]
                repo = client.post(REPOSITORY_PATH, body)
                cls.repos.append(repo)
                # Info about repo distributors is needed when publishing.
                repo = client.get(repo['_href'], params={'details': True})
                cls.repos[-1] = repo
        except:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        """Clean up resources created during the test."""
        client = api.Client(cls.cfg)
        for repo in cls.repos:
            client.delete(repo['_href'])
        client.delete(ORPHANS_PATH)

    def test_01_upload_publish(self):
        """Upload an RPM to the first repository, and publish it.

        Execute :meth:`verify_repo_search` and :meth:`verify_repo_download`.
        """
        repo = self.repos[0]
        utils.upload_import_unit(
            self.cfg,
            self.rpm,
            {'unit_type_id': 'rpm'},
            repo,
        )
        utils.publish_repo(self.cfg, repo)
        with self.subTest():
            self.verify_repo_search(repo)
        with self.subTest():
            self.verify_repo_download(repo)

    def test_02_copy_publish(self):
        """Copy and RPM from the first repo to the second, and publish it.

        Execute :meth:`verify_repo_search` and :meth:`verify_repo_download`.
        """
        api.Client(self.cfg).post(
            urljoin(self.repos[1]['_href'], 'actions/associate/'),
            {'source_repo_id': self.repos[0]['id']}
        )
        utils.publish_repo(self.cfg, self.repos[1])
        with self.subTest():
            self.verify_repo_search(self.repos[1])
        with self.subTest():
            self.verify_repo_download(self.repos[1])

    def test_03_compare_repos(self):
        """Verify the two repositories contain the same content unit."""
        repo_0_units = utils.search_units(self.cfg, self.repos[0])
        repo_1_units = utils.search_units(self.cfg, self.repos[1])
        self.assertEqual(
            repo_0_units[0]['unit_id'],
            repo_1_units[0]['unit_id'],
        )

    def verify_repo_search(self, repo):
        """Search for units in the given ``repo``.

        Verify that only one content unit is in ``repo``, and that several of
        its metadata attributes are correct. This test targets `Pulp #2365
        <https://pulp.plan.io/issues/2365>`_.
        """
        units = utils.search_units(self.cfg, repo)
        self.assertEqual(len(units), 1)

        # filename and derived attributes
        with self.subTest():
            self.assertEqual(units[0]['metadata']['filename'], RPM)
        with self.subTest():
            self.assertEqual(units[0]['metadata']['epoch'], '0')
        with self.subTest():
            self.assertEqual(units[0]['metadata']['name'], 'bear')
        with self.subTest():
            self.assertEqual(units[0]['metadata']['version'], '4.1')
        with self.subTest():
            self.assertEqual(units[0]['metadata']['release'], '1')

        # other attributes
        with self.subTest():
            self.assertEqual(units[0]['metadata']['license'], 'GPLv2')
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['description'],
                'A dummy package of bear',
            )
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['files'],
                {'dir': [], 'file': ['/tmp/bear.txt']},
            )

    def verify_repo_download(self, repo):
        """Download :data:`pulp_smash.constants.RPM` from the given ``repo``.

        Verify that it is exactly equal to the one uploaded earlier.
        """
        repo_rpm = get_unit(self.cfg, repo['distributors'][0], RPM).content
        self.assertEqual(self.rpm, repo_rpm)


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
        if check_issue_2387(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2387')
        if check_issue_2277(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        cls.erratum = gen_erratum()

        # Create an RPM repository with a feed and distributor.
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Sync content into the repository, and give it an erratum.
        utils.sync_repo(cls.cfg, repo['_href'])
        utils.upload_import_erratum(cls.cfg, cls.erratum, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})

        # Publish the repository, and fetch and parse updateinfo.xml
        utils.publish_repo(cls.cfg, repo)
        cls.updateinfo = (
            get_repodata(cls.cfg, repo['distributors'][0], 'updateinfo')
        )

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
