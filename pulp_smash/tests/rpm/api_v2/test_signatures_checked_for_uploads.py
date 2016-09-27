# coding=utf-8
"""Tests for repository importer signature checks.

As of Pulp 2.10, it's possible to configure an RPM repository importer to
perform checks on all synced-in and uploaded packages. Two new importer options
are available:

``require_signature``
    A boolean. If true, imported packages must be signed with a key listed in
    ``allowed_keys``.
``allowed_keys``
    A list of 32-bit key IDs, as hex characters. (e.g. ``["deadbeef"]``) An
    empty list is treated as the list of all possible key IDs.

Beware that if a package has a signature, its signature *must* be listed in
``allowed_keys``, even when ``require_signature`` is false. The only importer
configuration that allows all packages is ``{'require_signature': False,
'allowed_keys': []}``.

To test this feature, importers with at least the following options should be
created::

    {'require_signature': False, 'allowed_keys': ['invalid key id']}
    {'require_signature': False, 'allowed_keys': ['valid key id']}
    {'require_signature': False, 'allowed_keys': []}
    {'require_signature': True, 'allowed_keys': ['invalid key id']}
    {'require_signature': True, 'allowed_keys': ['valid key id']}
    {'require_signature': True, 'allowed_keys': []}

In addition, at least the following types of packages should be imported::

* Signed DRPMs
* Signed RPMs
* Signed SRPMs
* Unsigned DRPMs
* Unsigned RPMs
* Unsigned SRPMs

Finally, importer options may be changed in some circumstances, and Pulp should
gracefully handle those changes.

For more information, see `Pulp #1991`_ and `Pulp Smash #347`_.

.. _Pulp #1991: https://pulp.plan.io/issues/1991
.. _Pulp Smash #347: https://github.com/PulpQE/pulp-smash/issues/347
"""
import unittest
from itertools import chain

from requests.exceptions import HTTPError

from pulp_smash import api, config, exceptions, selectors, utils
from pulp_smash.constants import (
    DRPM_UNSIGNED_URL,
    DRPM_URL,
    PULP_FIXTURES_KEY_ID,
    REPOSITORY_PATH,
    RPM_UNSIGNED_URL,
    RPM_URL,
    SRPM_UNSIGNED_URL,
    SRPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module


_INVALID_KEY_ID = '01234567'
_SIGNED_PACKAGES = {}  # e.g. {'rpm': …, 'srpm': …}
_UNSIGNED_PACKAGES = {}


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip tests. Cache packages to be uploaded to repos.

    Skip the tests in this module if:

    * The RPM plugin is unsupported.
    * `Pulp #1991 <https://pulp.plan.io/issues/1991>`_ is untestable for the
      version of Pulp under test.
    """
    cfg = config.get_config()
    if selectors.bug_is_untestable(1991, cfg.version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/1991')
    set_up_module()
    try:
        _SIGNED_PACKAGES['rpm'] = utils.http_get(RPM_URL)
        _SIGNED_PACKAGES['srpm'] = utils.http_get(SRPM_URL)
        _UNSIGNED_PACKAGES['rpm'] = utils.http_get(RPM_UNSIGNED_URL)
        _UNSIGNED_PACKAGES['srpm'] = utils.http_get(SRPM_UNSIGNED_URL)
        if selectors.bug_is_testable(1806, cfg.version):
            _SIGNED_PACKAGES['drpm'] = utils.http_get(DRPM_URL)
            _UNSIGNED_PACKAGES['drpm'] = utils.http_get(DRPM_UNSIGNED_URL)
    except:
        _SIGNED_PACKAGES.clear()
        _UNSIGNED_PACKAGES.clear()
        raise


def tearDownModule():  # pylint:disable=invalid-name
    """Delete the cached set of packages to be uploaded to repos."""
    _SIGNED_PACKAGES.clear()
    _UNSIGNED_PACKAGES.clear()


def _create_repository(cfg, importer_config):
    """Create an RPM repository with the given importer configuration.

    Return the repository's href.
    """
    body = gen_repo()
    body['importer_config'] = importer_config
    return api.Client(cfg).post(REPOSITORY_PATH, body).json()['_href']


# NOTE: We could inherit from unittest.TestCase and create a separate
# repository for each test method. This allows for better test isolation in
# case of failure. However, re-using just one repo per test case is faster, and
# it ensures that Pulp doesn't do anything tricky with deduplication logic.
class RequireValidKeyTestCase(utils.BaseAPITestCase):
    """Use an importer that requires signatures and has a valid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": ["valid key id"]}
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with an importer."""
        super(RequireValidKeyTestCase, cls).setUpClass()
        cls.repo_href = _create_repository(cls.cfg, {
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'require_signature': True,
        })
        cls.resources.add(cls.repo_href)

    def test_signed_packages(self):
        """Import signed DRPM, RPM and SRPM packages into the repository.

        Verify that each import succeeds.
        """
        for key, package in _SIGNED_PACKAGES.items():
            with self.subTest(key=key):
                utils.upload_import_unit(
                    self.cfg,
                    package,
                    key.split(' ')[-1],
                    self.repo_href,
                )

    def test_unsigned_packages(self):
        """Import unsigned DRPM, RPM and SRPM packages into the repository.

        Verify that each import fails.
        """
        for key, package in _UNSIGNED_PACKAGES.items():
            with self.subTest(key=key):
                with self.assertRaises(exceptions.TaskReportError):
                    utils.upload_import_unit(
                        self.cfg,
                        package,
                        key.split(' ')[-1],
                        self.repo_href,
                    )


class RequireInvalidKeyTestCase(utils.BaseAPITestCase):
    """Use an importer that requires signatures and has an invalid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": ["invalid key id"]}
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with an importer."""
        super(RequireInvalidKeyTestCase, cls).setUpClass()
        cls.repo_href = _create_repository(cls.cfg, {
            'allowed_keys': [_INVALID_KEY_ID],
            'require_signature': True,
        })
        cls.resources.add(cls.repo_href)

    def test_all_packages(self):
        """Import signed and unsigned DRPM, RPM & SRPM packages into the repo.

        Verify that each import fails.
        """
        for key, package in chain(
                _SIGNED_PACKAGES.items(),
                _UNSIGNED_PACKAGES.items()):
            with self.subTest(key=key):
                with self.assertRaises(exceptions.TaskReportError):
                    utils.upload_import_unit(
                        self.cfg,
                        package,
                        key.split(' ')[-1],
                        self.repo_href,
                    )


class RequireAnyKeyTestCase(utils.BaseAPITestCase):
    """Use an importer that requires signatures and has no key IDs.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": true, "allowed_keys": []}
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with an importer."""
        super(RequireAnyKeyTestCase, cls).setUpClass()
        cls.repo_href = _create_repository(cls.cfg, {
            'allowed_keys': [],
            'require_signature': True,
        })
        cls.resources.add(cls.repo_href)

    def test_signed_packages(self):
        """Import signed DRPM, RPM and SRPM packages into the repo.

        Verify that each import succeeds.
        """
        for key, package in _SIGNED_PACKAGES.items():
            with self.subTest(key=key):
                utils.upload_import_unit(
                    self.cfg,
                    package,
                    key.split(' ')[-1],
                    self.repo_href,
                )

    def test_unsigned_packages(self):
        """Import unsigned DRPM, RPM and SRPM packages into the repo.

        Verify that each import fails.
        """
        for key, package in _UNSIGNED_PACKAGES.items():
            with self.subTest(key=key):
                with self.assertRaises(exceptions.TaskReportError):
                    utils.upload_import_unit(
                        self.cfg,
                        package,
                        key.split(' ')[-1],
                        self.repo_href,
                    )


class AllowInvalidKeyTestCase(utils.BaseAPITestCase):
    """Use an importer that allows unsigned packages and has an invalid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": ["invalid key id"]}
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with an importer."""
        super(AllowInvalidKeyTestCase, cls).setUpClass()
        cls.repo_href = _create_repository(cls.cfg, {
            'allowed_keys': [_INVALID_KEY_ID],
            'require_signature': False,
        })
        cls.resources.add(cls.repo_href)

    def test_signed_packages(self):
        """Import signed DRPM, RPM and SRPM packages into the repository.

        Verify that each import fails.
        """
        for key, package in _SIGNED_PACKAGES.items():
            with self.subTest(key=key):
                with self.assertRaises(exceptions.TaskReportError):
                    utils.upload_import_unit(
                        self.cfg,
                        package,
                        key.split(' ')[-1],
                        self.repo_href,
                    )

    def test_unsigned_packages(self):
        """Import unsigned DRPM, RPM and SRPM packages into the repository.

        Verify that each import succeeds.
        """
        for key, package in _UNSIGNED_PACKAGES.items():
            with self.subTest(key=key):
                utils.upload_import_unit(
                    self.cfg,
                    package,
                    key.split(' ')[-1],
                    self.repo_href,
                )


class AllowValidKeyTestCase(utils.BaseAPITestCase):
    """Use an importer that allows unsigned packages and has a valid key ID.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": ["valid key id"]}
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with an importer."""
        super(AllowValidKeyTestCase, cls).setUpClass()
        cls.repo_href = _create_repository(cls.cfg, {
            'allowed_keys': [PULP_FIXTURES_KEY_ID],
            'require_signature': False,
        })
        cls.resources.add(cls.repo_href)

    def test_all_packages(self):
        """Import signed and unsigned DRPM, RPM & SRPM packages into the repo.

        Verify that each import succeeds.
        """
        for key, package in chain(
                _SIGNED_PACKAGES.items(),
                _UNSIGNED_PACKAGES.items()):
            with self.subTest(key=key):
                utils.upload_import_unit(
                    self.cfg,
                    package,
                    key.split(' ')[-1],
                    self.repo_href,
                )


class AllowAnyKeyTestCase(utils.BaseAPITestCase):
    """Use an importer that allows unsigned packages and has no key IDs.

    The importer should have the following pseudocode configuration:

    .. code-block:: json

        {"require_signature": false, "allowed_keys": []}
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with an importer."""
        super(AllowAnyKeyTestCase, cls).setUpClass()
        cls.repo_href = _create_repository(cls.cfg, {
            'allowed_keys': [],
            'require_signature': False,
        })
        cls.resources.add(cls.repo_href)

    def test_all_packages(self):
        """Import signed and unsigned DRPM, RPM & SRPM packages into the repo.

        Verify that each import succeeds.
        """
        for key, package in chain(
                _SIGNED_PACKAGES.items(),
                _UNSIGNED_PACKAGES.items()):
            with self.subTest(key=key):
                utils.upload_import_unit(
                    self.cfg,
                    package,
                    key.split(' ')[-1],
                    self.repo_href,
                )


class KeyLengthTestCase(unittest.TestCase):
    """Verify pulp rejects key IDs that are not 32-bits long.

    An OpenPGP-compatible key ID (key fingerprint) is traditionally a 32-bit
    value. Newer OpenPGP key handling software allows for longer key IDs, and
    this is recommended, as it's extremely easy to find colliding key IDs.
    [1]_ However, Pulp allows only the short key IDs.

    .. [1] https://evil32.com/
    """

    def test_key_ids(self):
        """Create importers with key IDs shorter and longer than 32 bits.

        Pulp should prevent the importers from being created.
        """
        cfg = config.get_config()
        for allowed_key in ('0123456', '012345678'):
            with self.subTest(allowed_key=allowed_key):
                repo_href = None
                with self.assertRaises(HTTPError):
                    repo_href = _create_repository(cfg, {
                        'allowed_keys': [allowed_key]
                    })
                if repo_href is not None:
                    api.Client(cfg).delete(repo_href)
