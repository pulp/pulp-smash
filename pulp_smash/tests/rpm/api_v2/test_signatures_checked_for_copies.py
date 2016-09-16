# coding=utf-8
"""Tests for repository signature checks when copying packages.

This module mimics
:mod:`pulp_smash.tests.rpm.api_v2.test_signatures_checked_for_uploads`, except
that packages are primarily copied into repositories, instead of being
uploaded.

.. NOTE:: Pulp's signature checking logic is subtle. Please read
    :mod:`pulp_smash.tests.rpm.api_v2.test_signatures_checked_for_uploads`.
"""
# NOTE to test authors: the following procedure will result in two unique
# content units being stored by Pulp, where the two "bear" RPMs are identical
# aside from their signatures:
#
#     for word in signed unsigned; do
#       pulp-admin rpm repo uploads rpm --repo-id "$word" \
#         --file "${word}/bear-4.1-1.noarch.rpm"
#     done
#
# This module takes advantage of this behaviour. A pair of repositories is
# created, one containing a signed RPM, SRPM and DRPM, and the other containing
# the same three packages, but unsigned.
import inspect
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    DRPM_UNSIGNED_URL,
    DRPM_URL,
    ORPHANS_PATH,
    PULP_FIXTURES_KEY_ID,
    REPOSITORY_PATH,
    RPM_UNSIGNED_URL,
    RPM_URL,
    SRPM_UNSIGNED_URL,
    SRPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module


_REPOS = {}  # e.g. {'signed': {'_href': …}}
_SIGNED_PACKAGES = {}  # e.g. {'rpm': …, 'srpm': …}
_UNSIGNED_PACKAGES = {}


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip tests. Create repositories with fixture data."""
    cfg = config.get_config()
    if selectors.bug_is_untestable(1991, cfg.version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/1991')
    set_up_module()

    # Fetch RPMs.
    _SIGNED_PACKAGES['rpm'] = utils.http_get(RPM_URL)
    _SIGNED_PACKAGES['srpm'] = utils.http_get(SRPM_URL)
    _UNSIGNED_PACKAGES['rpm'] = utils.http_get(RPM_UNSIGNED_URL)
    _UNSIGNED_PACKAGES['srpm'] = utils.http_get(SRPM_UNSIGNED_URL)
    if selectors.bug_is_testable(1806, cfg.version):
        _SIGNED_PACKAGES['drpm'] = utils.http_get(DRPM_URL)
        _UNSIGNED_PACKAGES['drpm'] = utils.http_get(DRPM_UNSIGNED_URL)

    # Create repos, and upload RPMs to them.
    client = api.Client(cfg, api.json_handler)
    try:
        repo = client.post(REPOSITORY_PATH, gen_repo())
        _REPOS['signed'] = repo
        for type_id, pkg in _SIGNED_PACKAGES.items():
            utils.upload_import_unit(cfg, pkg, type_id, repo['_href'])

        repo = client.post(REPOSITORY_PATH, gen_repo())
        _REPOS['unsigned'] = repo
        for type_id, pkg in _UNSIGNED_PACKAGES.items():
            utils.upload_import_unit(cfg, pkg, type_id, repo['_href'])
    except:
        _SIGNED_PACKAGES.clear()
        _UNSIGNED_PACKAGES.clear()
        for _ in range(len(_REPOS)):
            client.delete(_REPOS.popitem()[1]['_href'])
        raise


def tearDownModule():  # pylint:disable=invalid-name
    """Delete repositories with fixture data."""
    _SIGNED_PACKAGES.clear()
    _UNSIGNED_PACKAGES.clear()
    client = api.Client(config.get_config())
    for _ in range(len(_REPOS)):
        client.delete(_REPOS.popitem()[1]['_href'])
    client.delete(ORPHANS_PATH)


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

    def create_populate_repo(self, importer_config, source_repo_id):
        """Create a repository, copy units into it and read it.

        In addition, schedule the repository for deletion with the
        ``addCleanup`` method. Return information about the repository.
        """
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = importer_config
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'source_repo_id': source_repo_id,
        })
        return client.get(repo['_href'])


class RequireValidKeyTestCase(_BaseTestCase):
    """Use an importer that requires signatures and has a valid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": ["valid key id"]}
    """

    def test_signed_packages(self):
        """Copy signed packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'require_signature': True,
        }, _REPOS['signed']['id'])
        content_unit_counts = {key: 1 for key in _SIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)

    def test_unsigned_packages(self):
        """Copy unsigned packages into a repository.

        Assert no packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'require_signature': True,
        }, _REPOS['unsigned']['id'])
        self.assertEqual(repo['content_unit_counts'], {})


class RequireInvalidKeyTestCase(_BaseTestCase):
    """Use an importer that requires signatures and has an invalid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": ["invalid key id"]}
    """

    def test_signed_packages(self):
        """Copy signed packages into a repository.

        Assert no packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': ['01234567'],
            'require_signature': True,
        }, _REPOS['signed']['id'])
        self.assertEqual(repo['content_unit_counts'], {})

    def test_unsigned_packages(self):
        """Copy unsigned packages into a repository.

        Assert no packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': ['01234567'],
            'require_signature': True,
        }, _REPOS['unsigned']['id'])
        self.assertEqual(repo['content_unit_counts'], {})


class RequireAnyKeyTestCase(_BaseTestCase):
    """Use an importer that requires signatures and has no key IDs.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": []}
    """

    def test_signed_packages(self):
        """Copy signed packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [],
            'require_signature': True,
        }, _REPOS['signed']['id'])
        content_unit_counts = {key: 1 for key in _SIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)

    def test_unsigned_packages(self):
        """Copy unsigned packages into a repository.

        Assert no packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [],
            'require_signature': True,
        }, _REPOS['unsigned']['id'])
        self.assertEqual(repo['content_unit_counts'], {})


class AllowInvalidKeyTestCase(_BaseTestCase):
    """Use an importer that allows unsigned packages and has an invalid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": ["invalid key id"]}
    """

    def test_signed_packages(self):
        """Copy signed packages into a repository.

        Assert no packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': ['01234567'],
            'require_signature': False,
        }, _REPOS['signed']['id'])
        self.assertEqual(repo['content_unit_counts'], {})

    def test_unsigned_packages(self):
        """Copy unsigned packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': ['01234567'],
            'require_signature': False,
        }, _REPOS['unsigned']['id'])
        content_unit_counts = {key: 1 for key in _UNSIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)


class AllowValidKeyTestCase(_BaseTestCase):
    """Use an importer that allows unsigned packages and has a valid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": ["valid key id"]}

    .. NOTE:: Pulp's signature checking logic is subtle. Please read
        :mod:`pulp_smash.tests.rpm.api_v2.test_signatures_checked_for_uploads`.
    """

    def test_signed_packages(self):
        """Copy signed packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'require_signature': False,
        }, _REPOS['signed']['id'])
        content_unit_counts = {key: 1 for key in _SIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)

    def test_unsigned_packages(self):
        """Copy unsigned packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'require_signature': False,
        }, _REPOS['unsigned']['id'])
        content_unit_counts = {key: 1 for key in _UNSIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)


class AllowAnyKeyTestCase(_BaseTestCase):
    """Use an importer that allows unsigned packages and has no key IDs.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": []}
    """

    def test_signed_packages(self):
        """Copy signed packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [],
            'require_signature': False,
        }, _REPOS['signed']['id'])
        content_unit_counts = {key: 1 for key in _SIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)

    def test_unsigned_packages(self):
        """Copy unsigned packages into a repository.

        Assert packages are copied in.
        """
        repo = self.create_populate_repo({
            'allowed_keys': [],
            'require_signature': False,
        }, _REPOS['unsigned']['id'])
        content_unit_counts = {key: 1 for key in _UNSIGNED_PACKAGES.keys()}
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)
