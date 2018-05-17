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

from pulp_smash import api, config, exceptions, selectors, utils
from pulp_smash.constants import (
    DRPM,
    DRPM_UNSIGNED_URL,
    RPM,
    RPM_DATA,
    RPM_INVALID_URL,
    RPM_UNSIGNED_URL,
    RPM_WITH_VENDOR_DATA,
    RPM_WITH_VENDOR_FEED_URL,
    RPM_WITH_VENDOR_URL,
    SRPM,
    SRPM_UNSIGNED_URL,
)
from pulp_smash.pulp2.constants import ORPHANS_PATH, REPOSITORY_PATH
from pulp_smash.pulp2.utils import (
    BaseAPITestCase,
    publish_repo,
    search_units,
    sync_repo,
    upload_import_unit,
)
from pulp_smash.tests.pulp2.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_unit,
)
from pulp_smash.tests.pulp2.rpm.utils import check_issue_2620, check_issue_3104
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class UploadDrpmTestCase(unittest.TestCase):
    """Test whether one can upload a DRPM into a repository.

    Specifically, this method does the following:

    1. Create a yum repository.
    2. Upload a DRPM into the repository.
    3. Search for all content units in the repository.

    This test case targets `Pulp Smash #336
    <https://github.com/PulpQE/pulp-smash/issues/336>`_
    """

    def test_all(self):
        """Import a DRPM into a repository and search it for content units."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(1806, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1806')
        client = api.Client(cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        self.addCleanup(client.delete, repo['_href'])
        drpm = utils.http_get(DRPM_UNSIGNED_URL)
        upload_import_unit(cfg, drpm, {'unit_type_id': 'drpm'}, repo)
        units = search_units(cfg, repo)

        # Test if DRPM has been uploaded successfully
        self.assertEqual(len(units), 1)

        # Test if DRPM extracted correct metadata for creating filename
        self.assertEqual(units[0]['metadata']['filename'], DRPM)


class UploadDrpmTestCaseWithCheckSumType(BaseAPITestCase):
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
        if selectors.bug_is_untestable(1806, self.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1806')
        if selectors.bug_is_untestable(2627, self.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2627')
        client = api.Client(self.cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        self.addCleanup(client.delete, repo['_href'])
        drpm = utils.http_get(DRPM_UNSIGNED_URL)
        upload_import_unit(
            self.cfg,
            drpm,
            {
                'unit_type_id': 'drpm',
                'unit_metadata': {'checksumtype': 'sha256'},
            },
            repo,
        )
        units = search_units(self.cfg, repo, {})
        self.assertEqual(len(units), 1, units)
        # Test if DRPM extracted correct metadata for creating filename.
        self.assertEqual(
            units[0]['metadata']['filename'],
            DRPM,
        )


class UploadedDrpmChecksumTypeTestCase(unittest.TestCase):
    """Verify uploaded DRPMs have checksums of the requested type."""

    def test_all(self):
        """Verify uploaded DRPMs have checksums of the requested type.

        Specifically, this method does the following:

        1. Create a yum repository.
        2. Upload a DRPM into the repository with "checksumtype" set to
           "md5".
        3. Assert that "checksumtype" was set to "md5".
        4. Assert that checksum value was calculated according to "md5".

        This test targets:

        * `Pulp #2774 <https://pulp.plan.io/issues/2774>`_
        * `Pulp Smash #663 <https://github.com/PulpQE/pulp-smash/issues/663>`_
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        drpm = utils.http_get(DRPM_UNSIGNED_URL)
        upload_import_unit(cfg, drpm, {
            'unit_metadata': {'checksumtype': 'md5'},
            'unit_type_id': 'drpm',
        }, repo)
        units = search_units(cfg, repo)

        with self.subTest(comment='verify checksumtype'):
            self.assertEqual(units[0]['metadata']['checksumtype'], 'md5')
        with self.subTest(comment='verify checksum'):
            if selectors.bug_is_untestable(2774, cfg.pulp_version):
                self.skipTest('https://pulp.plan.io/issues/2774')
            self.assertEqual(
                units[0]['metadata']['checksum'],
                units[0]['metadata']['checksums']['md5']
            )


class UploadSrpmTestCase(BaseAPITestCase):
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
        upload_import_unit(cls.cfg, srpm, {'unit_type_id': 'srpm'}, repo)
        cls.units = search_units(cls.cfg, repo, {}, api.safe_handler)

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


class UploadRpmTestCase(BaseAPITestCase):
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
        if check_issue_3104(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/3104')
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
        except:  # noqa:E722
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
        upload_import_unit(
            self.cfg,
            self.rpm,
            {'unit_type_id': 'rpm'},
            repo,
        )
        publish_repo(self.cfg, repo)
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
        publish_repo(self.cfg, self.repos[1])
        self.verify_repo_search(self.repos[1])
        self.verify_repo_download(self.repos[1])

    def test_03_compare_repos(self):
        """Verify the two repositories contain the same content unit."""
        repo_0_units = search_units(self.cfg, self.repos[0])
        repo_1_units = search_units(self.cfg, self.repos[1])
        self.assertEqual(
            repo_0_units[0]['unit_id'],
            repo_1_units[0]['unit_id'],
        )

    def verify_repo_search(self, repo):
        """Search for units in the given ``repo``.

        Verify that only one content unit is in ``repo``, and that several of
        its metadata attributes are correct. This test targets `Pulp #2365
        <https://pulp.plan.io/issues/2365>`_ and `Pulp #2754
        <https://pulp.plan.io/issues/2754>`_
        """
        units = search_units(self.cfg, repo)
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

        if selectors.bug_is_testable(2754, self.cfg.pulp_version):
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


class VendorInfoTestCase(unittest.TestCase):
    """Test whether the vendor info is present in case of sync and upload.

    This tests case targets the following issues:

    * `Pulp Smash #680 <https://github.com/PulpQE/pulp-smash/issues/680>`_
    * `Pulp #2781 <https://pulp.plan.io/issues/2781>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if selectors.bug_is_untestable(2781, cls.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2781')

    def test_upload(self):
        """Test whether Pulp recognizes an uploaded RPM's vendor information.

        Create a repository, upload an RPM with a non-null vendor, and perform
        several checks. See :meth:`do_test`.
        """
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        rpm = utils.http_get(RPM_WITH_VENDOR_URL)
        upload_import_unit(self.cfg, rpm, {'unit_type_id': 'rpm'}, repo)
        self.do_test(repo)

    def test_sync(self):
        """Test whether Pulp recognizes a synced RPM's vendor information.

        Create a repository, sync in an RPM with a non-null vendor, and perform
        several checks. See :meth:`do_test`.
        """
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_WITH_VENDOR_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        self.do_test(repo)

    def do_test(self, repo):
        """Verify that the given ``repo`` has an RPM with vendor data.

        Perform the following checks:

        * Search ``repo`` for RPMs and filter with a valid unit license. Assert
          that one search result is returned, and that it has vendor metadata.
        * Search ``repo`` for RPMs and filter with a valid unit vendor. Assert
          that one search result is returned, and that it has vendor metadata.
        * Search ``repo`` for RPMs and filter with an invalid unit license.
          Assert that no search results are returned.
        * Search ``repo`` for RPMs and filter with an invalid unit vendor.
          Assert that no search results are returned.

        The license-based searches serve as a sanity check. They show that the
        search syntax is correct.
        """
        with self.subTest(comment='filter with a valid unit license'):
            units = search_units(self.cfg, repo, {
                'filters': {'unit': {
                    'license': RPM_WITH_VENDOR_DATA['metadata']['license']
                }},
                'type_ids': ['rpm'],
            })
            self._verify_search_results(units)

        with self.subTest(comment='filter with a valid unit vendor'):
            units = search_units(self.cfg, repo, {
                'filters': {'unit': {
                    'vendor': RPM_WITH_VENDOR_DATA['metadata']['vendor']
                }},
                'type_ids': ['rpm'],
            })
            self._verify_search_results(units)

        with self.subTest(comment='filter with an invalid unit license'):
            units = search_units(self.cfg, repo, {
                'filters': {'unit': {'license': utils.uuid4()}},
                'type_ids': ['rpm'],
            })
            self.assertEqual(len(units), 0, units)

        with self.subTest(comment='filter with an invalid unit vendor'):
            units = search_units(self.cfg, repo, {
                'filters': {'unit': {'vendor': utils.uuid4()}},
                'type_ids': ['rpm'],
            })
            self.assertEqual(len(units), 0, units)

    def _verify_search_results(self, units):
        """Assert that ``units`` contains one entry with a correct vendor."""
        self.assertEqual(len(units), 1, units)
        self.assertIn('vendor', units[0]['metadata'])
        self.assertEqual(
            units[0]['metadata']['vendor'],
            RPM_WITH_VENDOR_DATA['metadata']['vendor'],
        )


class UploadInvalidRPMTestCase(unittest.TestCase):
    """Test that upload fails and error is raised when upload invalid RPM."""

    def test_all(self):
        """Test whether one invalid RPM upload fails and produces error details.

        This test targets the following issues.

        * `Pulp Smash #544 <https://github.com/PulpQE/pulp-smash/issues/544>`_
        * `Pulp #2543 <https://pulp.plan.io/issues/2543>`_
        * `Pulp #3090 <https://pulp.plan.io/issues/3090>`_

        Do the following:

        1. Create a RPM repository.
        2. Upload an invalid RPM to repository. Assert that upload fails, and
           that the returned error contains a descriptive message.
        3. Verify that the repository contains no RPMs.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(2543, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2543')
        if selectors.bug_is_untestable(3090, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3090')
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        # Upload invalid RPM
        rpm = utils.http_get(RPM_INVALID_URL)
        with self.assertRaises(exceptions.TaskReportError) as context:
            upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)
        task = context.exception.task

        # Assert that rturned error contains a descriptive message
        self.assertIsNotNone(task['error']['description'])
        self.assertIn('upload', task['error']['description'])

        # Verify that the repository contains no RPMs
        rpm = search_units(cfg, repo, {'type_ids': ('rpm',)})
        self.assertEqual(len(rpm), 0)
