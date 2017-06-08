# coding=utf-8
"""Tests for repository signature checks when syncing packages.

This module mimics
:mod:`pulp_smash.tests.rpm.api_v2.test_signatures_checked_for_uploads`, except
that packages are synced in to Pulp instead of being uploaded.

.. NOTE:: Pulp's signature checking logic is subtle. Please read
    :mod:`pulp_smash.tests.rpm.api_v2.test_signatures_checked_for_uploads`.
"""
# NOTE to test authors: It's important to remove all content units after each
# test. Let's say that you create a repository with an importer that requires
# signatures and with a feed pointing at a repository with unsigned RPMs. When
# this repository is synced, none of the RPMs from the remote repository will
# be added. However, if Pulp has local content units matching what's listed in
# the remote repository's `repodata` directory, then the local content units
# will be added to the repository.
#
# The easiest way to avoid these confusing situations is to ensure that Pulp
# retains no local content units after each test.
import inspect
import unittest

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    DRPM_SIGNED_FEED_COUNT,
    DRPM_SIGNED_FEED_URL,
    DRPM_UNSIGNED_FEED_COUNT,
    DRPM_UNSIGNED_FEED_URL,
    ORPHANS_PATH,
    PULP_FIXTURES_KEY_ID,
    REPOSITORY_PATH,
    RPM_SIGNED_FEED_COUNT,
    RPM_SIGNED_FEED_URL,
    RPM_UNSIGNED_FEED_COUNT,
    RPM_UNSIGNED_FEED_URL,
    SRPM_SIGNED_FEED_COUNT,
    SRPM_SIGNED_FEED_URL,
    SRPM_UNSIGNED_FEED_COUNT,
    SRPM_UNSIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip tests."""
    if selectors.bug_is_untestable(1991, config.get_config().version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/1991')
    if selectors.bug_is_untestable(2242, config.get_config().version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2242')
    set_up_module()


def tearDownModule():  # pylint:disable=invalid-name
    """Delete orphan content units."""
    api.Client(config.get_config()).delete(ORPHANS_PATH)


class _BaseTestCase(unittest.TestCase):
    """Common logic for the test cases in this module."""

    @classmethod
    def setUpClass(cls):
        """Skip this test case if no child inherits from it."""
        if inspect.getmro(cls)[0] == _BaseTestCase:
            raise unittest.SkipTest('Abstract base class.')

    def setUp(self):
        """Set common variables."""
        self.cfg = config.get_config()

    def create_sync_repo(self, importer_config):
        """Create and sync a repository, and schedule tear-down logic.

        The tear-down logic deletes the created repository and all orphans.
        (``addCleanup()`` is used.) An up-to-date dict of information about the
        repo is returned.
        """
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = importer_config
        self.addCleanup(client.delete, ORPHANS_PATH)
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(self.cfg, repo)
        return client.get(repo['_href'])


class RequireValidKeyTestCase(_BaseTestCase):
    """Use an importer that requires signatures and has a valid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": ["valid key id"]}
    """

    def test_signed_rpm(self):
        """Sync signed RPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': RPM_SIGNED_FEED_URL,
            'require_signature': True,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_drpm(self):
        """Sync signed DRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': DRPM_SIGNED_FEED_URL,
            'require_signature': True,
        })['content_unit_counts']
        self.assertEqual(cu_counts['drpm'], DRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_srpm(self):
        """Sync signed SRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': SRPM_SIGNED_FEED_URL,
            'require_signature': True,
        })['content_unit_counts']
        self.assertEqual(cu_counts['srpm'], SRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_packages(self):
        """Sync unsigned RPMs, DRPMs and SRPMS into repositories.

        Assert no packages are synced in.
        """
        variants = (
            (RPM_UNSIGNED_FEED_URL, 'rpm'),
            (DRPM_UNSIGNED_FEED_URL, 'drpm'),
            (SRPM_UNSIGNED_FEED_URL, 'srpm'),
        )
        for feed, type_id in variants:
            with self.subTest(type_id=type_id):
                cu_counts = self.create_sync_repo({
                    'allowed_keys': [PULP_FIXTURES_KEY_ID],
                    'feed': feed,
                    'require_signature': True,
                })['content_unit_counts']
                self.assertNotIn(type_id, cu_counts)


class RequireInvalidKeyTestCase(_BaseTestCase):
    """Use an importer that requires signatures and has an invalid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": ["invalid key id"]}
    """

    def test_packages(self):
        """Sync signed and unsigned RPMs, DRPMs and SRPMs into repositories.

        Assert no packages are synced in.
        """
        variants = (
            (RPM_SIGNED_FEED_URL, 'rpm'),
            (DRPM_SIGNED_FEED_URL, 'drpm'),
            (SRPM_SIGNED_FEED_URL, 'srpm'),
            (RPM_UNSIGNED_FEED_URL, 'rpm'),
            (DRPM_UNSIGNED_FEED_URL, 'drpm'),
            (SRPM_UNSIGNED_FEED_URL, 'srpm'),
        )
        for feed, type_id in variants:
            with self.subTest(type_id=type_id):
                cu_counts = self.create_sync_repo({
                    'allowed_keys': ['01234567'],
                    'feed': feed,
                    'require_signature': True,
                })['content_unit_counts']
                self.assertNotIn(type_id, cu_counts)


class RequireAnyKeyTestCase(_BaseTestCase):
    """Use an importer that requires signatures and has no key IDs.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": []}
    """

    def test_signed_rpm(self):
        """Sync signed RPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': RPM_SIGNED_FEED_URL,
            'require_signature': True,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_drpm(self):
        """Sync signed DRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': DRPM_SIGNED_FEED_URL,
            'require_signature': True,
        })['content_unit_counts']
        self.assertEqual(cu_counts['drpm'], DRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_srpm(self):
        """Sync signed SRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': SRPM_SIGNED_FEED_URL,
            'require_signature': True,
        })['content_unit_counts']
        self.assertEqual(cu_counts['srpm'], SRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_packages(self):
        """Sync unsigned RPMs, DRPMs and SRPMS into repositories.

        Assert no packages are synced in.
        """
        variants = (
            (RPM_UNSIGNED_FEED_URL, 'rpm'),
            (DRPM_UNSIGNED_FEED_URL, 'drpm'),
            (SRPM_UNSIGNED_FEED_URL, 'srpm'),
        )
        for feed, type_id in variants:
            with self.subTest(type_id=type_id):
                cu_counts = self.create_sync_repo({
                    'allowed_keys': [],
                    'feed': feed,
                    'require_signature': True,
                })['content_unit_counts']
                self.assertNotIn(type_id, cu_counts)


class AllowInvalidKeyTestCase(_BaseTestCase):
    """Use an importer that allows unsigned packages and has an invalid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": ["invalid key id"]}
    """

    def test_signed_packages(self):
        """Import signed RPMs, DRPMs and SRPMs into repositories.

        Assert no packages are synced.
        """
        variants = (
            (RPM_SIGNED_FEED_URL, 'rpm'),
            (DRPM_SIGNED_FEED_URL, 'drpm'),
            (SRPM_SIGNED_FEED_URL, 'srpm'),
        )
        for feed, type_id in variants:
            with self.subTest(type_id=type_id):
                cu_counts = self.create_sync_repo({
                    'allowed_keys': ['01234567'],
                    'feed': feed,
                    'require_signature': False,
                })['content_unit_counts']
                self.assertNotIn(type_id, cu_counts)

    def test_unsigned_rpms(self):
        """Import unsigned RPMs into a repository.

        Assert packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': ['01234567'],
            'feed': RPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_UNSIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_drpms(self):
        """Import unsigned DRPMs into a repository.

        Assert packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': ['01234567'],
            'feed': DRPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(
            cu_counts['drpm'],
            DRPM_UNSIGNED_FEED_COUNT,
            cu_counts,
        )

    def test_unsigned_srpms(self):
        """Import unsigned SRPMs into a repository.

        Assert packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': ['01234567'],
            'feed': SRPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(
            cu_counts['srpm'],
            SRPM_UNSIGNED_FEED_COUNT,
            cu_counts,
        )


class AllowValidKeyTestCase(_BaseTestCase):
    """Use an importer that allows unsigned packages and has a valid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": ["valid key id"]}

    .. NOTE:: Pulp's signature checking logic is subtle. Please read
        :mod:`pulp_smash.tests.rpm.api_v2.test_signatures_checked_for_uploads`.
    """

    def test_signed_rpm(self):
        """Sync signed RPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': RPM_SIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_drpm(self):
        """Sync signed DRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': DRPM_SIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['drpm'], DRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_srpm(self):
        """Sync signed SRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': SRPM_SIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['srpm'], SRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_rpms(self):
        """Import unsigned RPMs into a repository.

        Assert packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': RPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_UNSIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_drpms(self):
        """Import unsigned DRPMs into a repository.

        Assert packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': DRPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(
            cu_counts['drpm'],
            DRPM_UNSIGNED_FEED_COUNT,
            cu_counts
        )

    def test_unsigned_srpms(self):
        """Import unsigned SRPMs into a repository.

        Assert packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'feed': SRPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(
            cu_counts['srpm'],
            SRPM_UNSIGNED_FEED_COUNT,
            cu_counts,
        )


class AllowAnyKeyTestCase(_BaseTestCase):
    """Use an importer that allows unsigned packages and has no key IDs.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": []}
    """

    def test_signed_rpm(self):
        """Sync signed RPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': RPM_SIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_drpm(self):
        """Sync signed DRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': DRPM_SIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['drpm'], DRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_signed_srpm(self):
        """Sync signed SRPMs into the repository.

        Assert packages are synced in.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': SRPM_SIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['srpm'], SRPM_SIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_rpms(self):
        """Import unsigned RPMs into a repository.

        Verify packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': RPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(cu_counts['rpm'], RPM_UNSIGNED_FEED_COUNT, cu_counts)

    def test_unsigned_drpms(self):
        """Import unsigned DRPMs into a repository.

        Verify packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': DRPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(
            cu_counts['drpm'],
            DRPM_UNSIGNED_FEED_COUNT,
            cu_counts
        )

    def test_unsigned_srpms(self):
        """Import unsigned SRPMs into a repository.

        Verify packages are synced.
        """
        cu_counts = self.create_sync_repo({
            'allowed_keys': [],
            'feed': SRPM_UNSIGNED_FEED_URL,
            'require_signature': False,
        })['content_unit_counts']
        self.assertEqual(
            cu_counts['srpm'],
            SRPM_UNSIGNED_FEED_COUNT,
            cu_counts,
        )
