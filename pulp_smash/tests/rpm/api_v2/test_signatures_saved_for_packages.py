# coding=utf-8
"""Tests for how well Pulp can deal with package signatures.

When a package is added to an RPM repository, its signature should be stored by
Pulp. This is true regardless of whether the package is an RPM, DRPM or SRPM.

Tests for this feature include the following:

* Upload signed and unsigned packages to RPM repositories. (See
  :class:`UploadPackageTestCase`.)
* Synchronize signed and unsigned packages to RPM repositories. (See
  :class:`SyncPackageTestCase`.)

For more information, see:

* `Pulp #1156 <https://pulp.plan.io/issues/1156>`_
"""
import inspect
import unittest
from urllib.parse import urljoin, urlparse

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    DRPM_FEED_URL,
    DRPM_UNSIGNED_FEED_URL,
    DRPM_UNSIGNED_URL,
    DRPM_URL,
    ORPHANS_PATH,
    PULP_FIXTURES_KEY_ID,
    REPOSITORY_PATH,
    RPM_FEED_URL,
    RPM_UNSIGNED_FEED_URL,
    RPM_UNSIGNED_URL,
    RPM_URL,
    SRPM_FEED_URL,
    SRPM_UNSIGNED_FEED_URL,
    SRPM_UNSIGNED_URL,
    SRPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _get_pkg_filename(pkg_url):
    """Given the URL of a package, return its filename."""
    return urlparse(pkg_url).path.split('/')[-1]


def _get_pkg_unit_type(pkg_filename):
    """Given the filename of package, return its unit type.

    :param pkg_url: A string such as 'bear-4.1-1.noarch.rpm'.
    :returns: A string such as 'rpm', 'srpm' or 'drpm'.
    """
    suffix = pkg_filename.split('.')[-2:]
    if suffix[-2] == 'src':
        return 'srpm'
    else:
        return suffix[-1]


class _BaseTestCase(unittest.TestCase):
    """An abstract base class for the test cases in this module."""

    @classmethod
    def setUpClass(cls):
        """Create a shared client."""
        if inspect.getmro(cls)[0] == _BaseTestCase:
            raise unittest.SkipTest('Abstract base class.')
        cls.cfg = config.get_config()
        if selectors.bug_is_untestable(1156, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1156')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def _find_unit(self, repo_href, pkg_url):
        """Search the given repository for a package.

        Search the repository for content units having the same filename as
        ``pkg_url``, verify only one result is found, and return it.
        """
        pkg_filename = _get_pkg_filename(pkg_url)
        pkg_unit_type = _get_pkg_unit_type(pkg_filename)
        if pkg_unit_type == 'drpm':
            # This is the location of the package relative to the repo root.
            pkg_filename = 'drpms/' + pkg_filename
        units = self.client.post(urljoin(repo_href, 'search/units/'), {
            'criteria': {
                'filters': {'unit': {'filename': {'$in': [pkg_filename]}}},
                'type_ids': [pkg_unit_type],
            }
        })
        self.assertEqual(len(units), 1)
        return units[0]

    def _verify_pkg_key(self, content_unit, key_id):
        """Verify the given content unit has the given key.

        :param content_unit: A single content unit as returned by a repository
            content unit search.
        :param key_id: A 32-bit OpenPGP key fingerprint, as a string.
        """
        unit_metadata = content_unit['metadata']
        self.assertIn('signing_key', unit_metadata)
        self.assertEqual(unit_metadata['signing_key'], key_id)


class UploadPackageTestCase(_BaseTestCase):
    """Test if Pulp saves signatures from uploaded packages."""

    def _create_repo_import_unit(self, pkg_url):
        """Create a repository, and import the given package into it.

        Schedule the repository and all orphan content units for deletion.
        Return the repository's href.
        """
        self.addCleanup(self.client.delete, ORPHANS_PATH)
        repo_href = self.client.post(REPOSITORY_PATH, gen_repo())['_href']
        self.addCleanup(self.client.delete, repo_href)

        pkg = utils.http_get(pkg_url)
        pkg_filename = _get_pkg_filename(pkg_url)
        pkg_unit_type = _get_pkg_unit_type(pkg_filename)
        utils.upload_import_unit(self.cfg, pkg, pkg_unit_type, repo_href)

        return repo_href

    def test_signed_drpm(self):
        """Import a signed DRPM into Pulp. Verify its signature."""
        if selectors.bug_is_untestable(1806, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1806')
        repo_href = self._create_repo_import_unit(DRPM_URL)
        unit = self._find_unit(repo_href, DRPM_URL)
        self._verify_pkg_key(unit, PULP_FIXTURES_KEY_ID)

    def test_signed_rpm(self):
        """Import a signed RPM into Pulp. Verify its signature."""
        repo_href = self._create_repo_import_unit(RPM_URL)
        unit = self._find_unit(repo_href, RPM_URL)
        self._verify_pkg_key(unit, PULP_FIXTURES_KEY_ID)

    def test_signed_srpm(self):
        """Import a signed SRPM into Pulp. Verify its signature."""
        repo_href = self._create_repo_import_unit(SRPM_URL)
        unit = self._find_unit(repo_href, SRPM_URL)
        self._verify_pkg_key(unit, PULP_FIXTURES_KEY_ID)

    def test_unsigned_drpm(self):
        """Import an unsigned DRPM into Pulp. Verify it has no signature."""
        if selectors.bug_is_untestable(1806, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1806')
        repo_href = self._create_repo_import_unit(DRPM_UNSIGNED_URL)
        unit = self._find_unit(repo_href, DRPM_UNSIGNED_URL)
        self.assertNotIn('signing_key', unit['metadata'])

    def test_unsigned_rpm(self):
        """Import an unsigned RPM into Pulp. Veriy it has no signature."""
        repo_href = self._create_repo_import_unit(RPM_UNSIGNED_URL)
        unit = self._find_unit(repo_href, RPM_UNSIGNED_URL)
        self.assertNotIn('signing_key', unit['metadata'])

    def test_unsigned_srpm(self):
        """Import an unsigned SRPM into Pulp. Verify it has no signature."""
        repo_href = self._create_repo_import_unit(SRPM_UNSIGNED_URL)
        unit = self._find_unit(repo_href, SRPM_UNSIGNED_URL)
        self.assertNotIn('signing_key', unit['metadata'])


class SyncPackageTestCase(_BaseTestCase):
    """Test if Pulp saves signatures from synced-in packages."""

    def _create_sync_repo(self, feed_url):
        """Create a repository with the given feed and sync it.

        Return the repository's href.
        """
        self.addCleanup(self.client.delete, ORPHANS_PATH)
        body = gen_repo()
        body['importer_config']['feed'] = feed_url
        repo_href = self.client.post(REPOSITORY_PATH, body)['_href']
        self.addCleanup(self.client.delete, repo_href)
        utils.sync_repo(self.cfg, repo_href)
        return repo_href

    def test_signed_drpm(self):
        """Assert signature is stored for signed drpm during sync."""
        repo_href = self._create_sync_repo(DRPM_FEED_URL)
        unit = self._find_unit(repo_href, DRPM_URL)
        self._verify_pkg_key(unit, PULP_FIXTURES_KEY_ID)

    def test_signed_rpm(self):
        """Assert signature is stored for signed rpm during sync."""
        repo_href = self._create_sync_repo(RPM_FEED_URL)
        unit = self._find_unit(repo_href, RPM_URL)
        self._verify_pkg_key(unit, PULP_FIXTURES_KEY_ID)

    def test_signed_srpm(self):
        """Assert signature is stored for signed srpm during sync."""
        repo_href = self._create_sync_repo(SRPM_FEED_URL)
        unit = self._find_unit(repo_href, SRPM_URL)
        self._verify_pkg_key(unit, PULP_FIXTURES_KEY_ID)

    def test_unsigned_drpm(self):
        """Assert no signature is stored for unsigned drpm during sync."""
        repo_href = self._create_sync_repo(DRPM_UNSIGNED_FEED_URL)
        unit = self._find_unit(repo_href, DRPM_UNSIGNED_URL)
        self.assertNotIn('signing_key', unit['metadata'])

    def test_unsigned_rpm(self):
        """Assert no signature is stored for unsigned rpm during sync."""
        repo_href = self._create_sync_repo(RPM_UNSIGNED_FEED_URL)
        unit = self._find_unit(repo_href, RPM_UNSIGNED_URL)
        self.assertNotIn('signing_key', unit['metadata'])

    def test_unsigned_srpm(self):
        """Assert no signature is stored for unsigned srpm during sync."""
        repo_href = self._create_sync_repo(SRPM_UNSIGNED_FEED_URL)
        unit = self._find_unit(repo_href, SRPM_UNSIGNED_URL)
        self.assertNotIn('signing_key', unit['metadata'])
