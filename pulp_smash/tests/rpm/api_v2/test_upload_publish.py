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
    RPM_DATA,
    RPM_WITH_VENDOR_URL,
    RPM_WITH_VENDOR_DATA,
    RPM_WITH_VENDOR,
    RPM_UNSIGNED_URL,
    SRPM,
    SRPM_UNSIGNED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_unit,
)
from pulp_smash.tests.rpm.utils import check_issue_2620
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


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


class UploadDrpmTestCaseWithCheckSumType(utils.BaseAPITestCase):
    """Test whether one can upload a DRPM into a repository.

    `Pulp issue #2627 <https://https://pulp.plan.io/issues/2627>`_ caused
    uploading to fail when "checksumtype" was specified.

    This test case targets `Pulp Smash #585
    <https://github.com/PulpQE/pulp-smash/issues/585>`_
    """

    @classmethod
    def setUpClass(cls):
        """Import a DRPM into a repository and search it for content units.

        Specifically, this method does the following:

        1. Create a yum repository.
        2. Upload a DRPM into the repository with "checksumtype" set to
            "sha256"
        3. Search for all content units in the repository.
        """
        super(UploadDrpmTestCaseWithCheckSumType, cls).setUpClass()

    def test_all(self):
        """Test that uploading DRPM with checksumtype specified works."""
        if selectors.bug_is_untestable(1806, self.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1806')
        if selectors.bug_is_untestable(2627, self.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2627')
        client = api.Client(self.cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        self.addCleanup(client.delete, repo['_href'])
        drpm = utils.http_get(DRPM_UNSIGNED_URL)
        utils.upload_import_unit(
            self.cfg,
            drpm,
            {
                'unit_type_id': 'drpm',
                'unit_metadata': {'checksumtype': 'sha256'},
            },
            repo,
        )
        units = utils.search_units(self.cfg, repo, {})
        self.assertEqual(len(units), 1, units)
        # Test if DRPM extracted correct metadata for creating filename.
        self.assertEqual(
            units[0]['metadata']['filename'],
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
        self.verify_repo_search(repo)
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
        self.verify_repo_search(self.repos[1])
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
        <https://pulp.plan.io/issues/2365>`_ and `Pulp #2754
        <https://pulp.plan.io/issues/2754>`_ and `Pulp #2781
        <https://pulp.plan.io/issues/2781>`_
        """
        units = utils.search_units(self.cfg, repo)
        self.assertEqual(len(units), 1)

        # filename and derived attributes
        with self.subTest():
            self.assertEqual(units[0]['metadata']['filename'], RPM)
        with self.subTest():
            self.assertEqual(units[0]['metadata']['epoch'], RPM_DATA['epoch'])
        with self.subTest():
            self.assertEqual(units[0]['metadata']['name'], RPM_DATA['name'])
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['version'],
                RPM_DATA['version']
            )
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['release'],
                RPM_DATA['release']
            )

        # other attributes
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['license'],
                RPM_DATA['metadata']['license']
            )
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['description'],
                RPM_DATA['metadata']['description'],
            )
        with self.subTest():
            self.assertEqual(
                units[0]['metadata']['files'],
                RPM_DATA['metadata']['files'],
            )

        if selectors.bug_is_testable(2754, self.cfg.version):
            # Test that additional fields are available.
            # Affected by Pulp issue #2754

            with self.subTest():
                self.assertEqual(
                    units[0]['metadata']['group'],
                    RPM_DATA['metadata']['group'],
                )
            with self.subTest():
                self.assertEqual(
                    units[0]['metadata']['summary'],
                    RPM_DATA['metadata']['summary'],
                )
            with self.subTest():
                self.assertEqual(
                    units[0]['metadata']['size'],
                    RPM_DATA['metadata']['size']['package'],
                )
            with self.subTest():
                self.assertEqual(
                    units[0]['metadata']['sourcerpm'],
                    RPM_DATA['metadata']['sourcerpm'],
                )

    def verify_repo_download(self, repo):
        """Download :data:`pulp_smash.constants.RPM` from the given ``repo``.

        Verify that it is exactly equal to the one uploaded earlier.
        """
        response = get_unit(self.cfg, repo['distributors'][0], RPM)
        with self.subTest():
            self.assertIn(
                response.headers['content-type'],
                ('application/octet-stream', 'application/x-rpm')
            )
        with self.subTest():
            self.assertEqual(self.rpm, response.content)


class UploadRetainsVendorData(utils.BaseAPITestCase):
    """Test whether one can upload, associate and publish RPMs.

    The test procedure is as follows:

    1. Create a repository.
    2. Upload an RPM to the first repository, and publish it.
    3. Test that RPM metadata includes all available fields, including vendor.
    """

    def test_all(self):
        """Create a pair of RPM repositories."""
        if selectors.bug_is_untestable(2781, self.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2781')
        rpm = utils.http_get(RPM_WITH_VENDOR_URL)
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)

        # Info about repo distributors is needed when publishing.
        repo = client.get(repo['_href'], params={'details': True})
        self.addCleanup(client.delete, repo['_href'])
        self.addCleanup(client.delete, ORPHANS_PATH)
        utils.upload_import_unit(
            self.cfg,
            rpm,
            {'unit_type_id': 'rpm'},
            repo,
        )
        utils.publish_repo(self.cfg, repo)
        units = utils.search_units(self.cfg, repo)
        with self.subTest(comment='Vendor info present and correct'):
            self.assertEqual(
                units[0]['metadata']['vendor'],
                RPM_WITH_VENDOR_DATA['metadata']['vendor'],
            )
        # filename and derived attributes
        with self.subTest(comment='Filename present and correct'):
            self.assertEqual(units[0]['metadata']['filename'], RPM_WITH_VENDOR)
        with self.subTest(comment='Epoch present and correct'):
            self.assertEqual(
                units[0]['metadata']['epoch'],
                RPM_WITH_VENDOR_DATA['epoch']
            )
        with self.subTest(comment='Name present and correct'):
            self.assertEqual(
                units[0]['metadata']['name'],
                RPM_WITH_VENDOR_DATA['name']
            )
        with self.subTest(comment='Version present and correct'):
            self.assertEqual(
                units[0]['metadata']['version'],
                RPM_WITH_VENDOR_DATA['version']
            )
        with self.subTest(comment='Release present and correct'):
            self.assertEqual(
                units[0]['metadata']['release'],
                RPM_WITH_VENDOR_DATA['release']
            )

        # other attributes
        with self.subTest(comment='License present and correct'):
            self.assertEqual(
                units[0]['metadata']['license'],
                RPM_WITH_VENDOR_DATA['metadata']['license']
            )
        with self.subTest(comment='Description present and correct'):
            self.assertEqual(
                units[0]['metadata']['description'],
                RPM_WITH_VENDOR_DATA['metadata']['description'],
            )
        with self.subTest(comment='File info present and correct'):
            self.assertEqual(
                units[0]['metadata']['files'],
                RPM_WITH_VENDOR_DATA['metadata']['files'],
            )
