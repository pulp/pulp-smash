# coding=utf-8
"""Tests for how well Pulp can deal with repository signature checks.

Pulp is able to run signature check when importing or associating
a package to a rpm repository based on the repository importer configurations.

Tests for this feature include the following:

* Associate a signed rpm to a repository with different
  repository importer configurations.
  (See :class:`AssociateUnsignedRPMTestCase`.)
* Associate an unsigned rpm to a repository with different
  repository importer configurations.
  (See :class:`AssociateSignedRPMTestCase`.)
* Import a signed rpm to a repository with different importer
  configurations (See :class:`ImportSignedRPMTestCase`.)
* Import an unsigned rpm to a repository with different importer
  configurations (See :class:`ImportUnsignedRPMTestCase`.)

For more information, see:

* `Pulp #1991 <https://pulp.plan.io/issues/1991>`_
"""
from __future__ import unicode_literals

import unittest2

from pulp_smash import api, selectors, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM_URL,
    RPM_UNSIGNED_URL
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_repo,
)

_REPO_CONFIGS = {
    'empty_allowed': {
        'allow_keys': [],
        'allow_unsigned': None
    },
    'matching_allowed': {
        'allow_keys': ['260f3a2b', 'f78fb195'],
        'allow_unsigned': None
    },
    'not_matching_allowed': {
        'allow_keys': ['1111111'],
        'allow_unsigned': None
    },
    'allow_unsigned': {
        'allow_keys': None,
        'allow_unsigned': True
    },
    'not_allow_unsigned': {
        'allow_keys': None,
        'allow_unsigned': False
    },
    'allow_unsigned_empty_allowed': {
        'allow_keys': [],
        'allow_unsigned': True
    },
}
"""A dict of different combinations of repo importer configurations."""


def _gen_repo_with_sig_options(allow_keys=None, allow_unsigned=None):
    """Return a dict with signature related importer configurations.

    For using in creating an RPM repository.
    """
    body = gen_repo()
    if allow_keys:
        body['importer_config']['allow_keys'] = allow_keys
    if allow_unsigned:
        body['importer_config']['allow_unsigned'] = allow_unsigned
    return body


class _BaseAssoicateRPMTestCase(utils.BaseAPITestCase):
    """Provides common setup behaviors and functions.

    For associating RPM tests.
    """

    @classmethod
    def setUpClass(cls, rpm_url, unit_type):  # pylint:disable=arguments-differ
        """Create RPM repositories."""
        super(_BaseAssoicateRPMTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1991, cls.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1991')
        cls.repos = {}
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.rpm_url = rpm_url
        cls.unit_type = unit_type

        # Create the original RPM repository that the RPM imported to
        repo = cls.client.post(REPOSITORY_PATH, gen_repo())
        cls.repos['origin'] = repo
        cls.resources.add(repo['_href'])

        # Create the RPM repositories with different importer configs.
        # The RPM will later be associated to those repositories.
        for repo_config in _REPO_CONFIGS:
            allow_keys = _REPO_CONFIGS[repo_config]['allow_keys']
            allow_unsigned = _REPO_CONFIGS[repo_config]['allow_unsigned']

            repo = cls.client.post(
                REPOSITORY_PATH,
                _gen_repo_with_sig_options(allow_keys, allow_unsigned)
            )
            cls.repos[repo_config] = repo
            cls.resources.add(repo['_href'])

        # Import the RPM to the original RPM repository
        utils.upload_import_unit(
            cls.cfg,
            utils.http_get(cls.rpm_url),
            'rpm',
            cls.repos['origin']['_href']
        )

    def _expect_success(self, task):
        """Verify if the association task succeeds."""
        self.assertTrue('units_successful' in task['result'])
        self.assertIsNone(task['error'])

    def _expect_fail(self, task):
        """Verify if the association task fails."""
        self.assertIsNotNone(task['error'])

    def _associate_pkg_and_validate(self, repo_type, expect_success):
        """Associate package to repo and verify result."""
        call_report = self.client.post(
            urljoin(self.repos[repo_type]['_href'], 'actions/associate/'),
            {
                'source_repo_id': self.repos['origin']['id'],
                'criteria': {
                    'type_ids': [self.unit_type],
                    'filters': {
                        'unit': {
                            'filename': {
                                '$in': [self.rpm_url.split('/')[-1]]
                            }
                        }
                    }
                }
            }
        )
        task = next(api.poll_spawned_tasks(self.cfg, call_report))
        if expect_success:
            self._expect_success(task)
        else:
            self._expect_fail(task)


class AssociateSignedRPMTestCase(_BaseAssoicateRPMTestCase):
    """Test how well Pulp can deal with signature check.

    When associating signed packages.
    """

    @classmethod
    def setUpClass(cls):  # pylint:disable=arguments-differ
        """Create RPM repositories."""
        super(AssociateSignedRPMTestCase, cls).setUpClass(RPM_URL, 'rpm')

    def test_empty_allowed(self):
        """Verify it fails to associate a signed RPM to the repo.

        Importer configs:
            'allow_keys': [],
        """
        self._associate_pkg_and_validate(
            repo_type='empty_allowed',
            expect_success=False)

    def test_matching_allowed(self):
        """Verify it succeeds to associate a signed RPM to the repo.

        Importer configs:
            'allow_keys': ['260f3a2b', 'f78fb195'],
        """
        self._associate_pkg_and_validate(
            repo_type='matching_allowed',
            expect_success=True)

    def test_no_matching_allowed(self):
        """Verify it fails to associate a signed RPM to the repo.

        Importer configs:
            'allow_keys': ['1111111']
        """
        self._associate_pkg_and_validate(
            repo_type='not_matching_allowed',
            expect_success=False)

    def test_allow_unsigned(self):
        """Verify it succeeds to associate a signed RPM to the repo.

        Importer configs:
            "allow_unsigned": True
        """
        self._associate_pkg_and_validate(
            repo_type='allow_unsigned',
            expect_success=True)

    def test_not_allow_unsigned(self):
        """Verify it succeeds to associate a signed RPM to the repo.

        Importer configs:
            "allow_unsigned": False
        """
        self._associate_pkg_and_validate(
            repo_type='not_allow_unsigned',
            expect_success=True)

    def test_allow_unsigned_emp_allowed(self):
        """Verify it fails to associate a signed RPM to the repo.

        Importer configs:
            "allow_keys": [],
            "allow_unsigned": True
        """
        self._associate_pkg_and_validate(
            repo_type='allow_unsigned_empty_allowed',
            expect_success=False)


class AssociateUnsignedRPMTestCase(_BaseAssoicateRPMTestCase):
    """Test how well Pulp can deal with signature check.

    When associating unsigned packages.
    """

    @classmethod
    def setUpClass(cls):  # pylint:disable=arguments-differ
        """Create RPM repositories."""
        super(AssociateUnsignedRPMTestCase, cls).setUpClass(
            RPM_UNSIGNED_URL,
            'rpm'
        )

    def test_empty_allow_keys(self):
        """Verify it succeeds to associate an unsigned RPM to the repo.

        Importer configs:
            "allow_keys": []
        """
        self._associate_pkg_and_validate(
            repo_type='empty_allowed',
            expect_success=True)

    def test_no_matching_allowed(self):
        """Verify it fails to associate an unsigned RPM to the repo.

        Importer configs:
            "allow_keys": ["1111111"]
        """
        self._associate_pkg_and_validate(
            repo_type='not_matching_allowed',
            expect_success=False)

    def test_allow_unsigned(self):
        """Verify it succeeds to associate an unsigned RPM to the repo.

        Importer configs:
            "allow_unsigned": True
        """
        self._associate_pkg_and_validate(
            repo_type='allow_unsigned',
            expect_success=True)

    def test_not_allow_unsigned(self):
        """Verify it succeeds to associate an unsigned RPM to the repo.

        Importer configs:
            "allow_unsigned": False
        """
        self._associate_pkg_and_validate(
            repo_type='not_allow_unsigned',
            expect_success=True)

    def test_allow_unsigned_emp_allowed(self):
        """Verify it succeeds to associate an unsigned RPM to the repo.

        Importer configs:
            "allow_keys": [],
            "allow_unsigned": True
        """
        self._associate_pkg_and_validate(
            repo_type='allow_unsigned_empty_allowed',
            expect_success=True)


class _BaseImportRPMTestCase(utils.BaseAPITestCase):
    """Provides common setup behaviors and functions.

    For importing RPM tests.
    """

    @classmethod
    def setUpClass(cls, rpm_url, unit_type):  # pylint:disable=arguments-differ
        """Set up common set-up and variables."""
        super(_BaseImportRPMTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1991, cls.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1991')

        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.rpm_url = rpm_url
        cls.unit_type = unit_type

    def setUp(self):
        """Set up common test variable."""
        self.repo = None

    def tearDown(self):
        """Delete repo and orphans after each test case."""
        # Note: Test methods are trying to import same package to
        # different target rpm repositories. In order to make sure Pulp
        # doesn't handle a package as a duplicate upload because of
        # the package uploaded in previous tests. Make sure the repo
        # and packages created are removed before running next tests.
        if self.repo:
            self.client.delete(self.repo['_href'])
        self.client.delete(ORPHANS_PATH)

    def create_repo(self, repo_type):
        """Create an RPM repository.

        With given signature related importer configurations.
        """
        allow_keys = _REPO_CONFIGS[repo_type]['allow_keys']
        allow_unsigned = _REPO_CONFIGS[repo_type]['allow_unsigned']

        return self.client.post(
            REPOSITORY_PATH,
            _gen_repo_with_sig_options(allow_keys, allow_unsigned)
        )

    def _expect_success(self, task):
        """Verify the upload_import task succeeds."""
        self.assertTrue('success_flag' in task['result'])
        self.assertTrue(task['result']['success_flag'])

    def _expect_fail(self, task):
        """Verify the upload_import task fails."""
        self.assertTrue('success_flag' in task['result'])
        self.assertFalse(task['result']['success_flag'])

    def _import_pkg_validate_result(self, repo_type, expect_success):
        """Import package and validate task result."""
        self.repo = self.create_repo(repo_type)

        call_report = utils.upload_import_unit(
            self.cfg,
            utils.http_get(self.rpm_url),
            self.unit_type,
            self.repo['_href']
        )
        task = next(api.poll_spawned_tasks(self.cfg, call_report))
        if expect_success:
            self._expect_success(task)
        else:
            self._expect_fail(task)


class ImportSignedRPMTestCase(_BaseImportRPMTestCase):
    """Test how well Pulp can deal with signature check.

    When importing signed packages.
    """

    @classmethod
    def setUpClass(cls):  # pylint:disable=arguments-differ
        """Set up common variables."""
        super(ImportSignedRPMTestCase, cls).setUpClass(RPM_URL, 'rpm')

    def test_empty_allow_keys_repo(self):
        """Verify it fails to import a signed RPM to the repo.

        Importer configs:
            "allow_keys": []
        """
        self._import_pkg_validate_result(
            repo_type='empty_allowed',
            expect_success=False)

    def test_matching_allow_keys_repo(self):
        """Verify it succeeds to import a signed RPM to the repo.

        Importer configs:
            "allow_keys": ["260f3a2b", "f78fb195"]
        """
        self._import_pkg_validate_result(
            repo_type='matching_allowed',
            expect_success=True)

    def test_no_matching_allowed(self):
        """Verify it fails to import a signed RPM to the repo.

        Importer configs:
            "allow_keys": ["1111111"]
        """
        self._import_pkg_validate_result(
            repo_type='not_matching_allowed',
            expect_success=False)

    def test_allow_unsigned_repo(self):
        """Verify it succeeds to import a signed RPM to the repo.

        Importer configs:
            "allow_unsigned": True
        """
        self._import_pkg_validate_result(
            repo_type='allow_unsigned',
            expect_success=True)

    def test_not_allow_unsigned_repo(self):
        """Verify it succeeds to import a signed RPM to the repo.

        Importer configs:
            "allow_unsigned": False
        """
        self._import_pkg_validate_result(
            repo_type='not_allow_unsigned',
            expect_success=True)

    def test_allow_unsigned_emp_allowed(self):
        """Verify it fails to import a signed RPM to the repo.

        Importer configs:
            "allow_keys": [],
            "allow_unsigned": True
        """
        self._import_pkg_validate_result(
            repo_type='allow_unsigned_empty_allowed',
            expect_success=False)


class ImportUnsignedRPMTestCase(_BaseImportRPMTestCase):
    """Test how well Pulp can deal with signature check.

    When importing unsigned packages.
    """

    @classmethod
    def setUpClass(cls):  # pylint:disable=arguments-differ
        """Set up common variables."""
        super(ImportUnsignedRPMTestCase, cls).setUpClass(
            RPM_UNSIGNED_URL,
            'rpm'
        )

    def test_empty_allowed(self):
        """Verify it succeeds to import an unsigned RPM to the repo.

        Importer configs:
            "allow_keys": [],
        """
        self._import_pkg_validate_result(
            repo_type='empty_allowed',
            expect_success=True)

    def test_not_matching_allowed(self):
        """Verify it fails to import an unsigned RPM to the repo.

        Importer configs:
            "allow_keys": ["1111111"],
        """
        self._import_pkg_validate_result(
            repo_type='not_matching_allowed',
            expect_success=False)

    def test_allow_unsigned(self):
        """Verify it succeeds to import an unsigned RPM to the repo.

        Importer configs:
            "allow_unsigned": True,
        """
        self._import_pkg_validate_result(
            repo_type='allow_unsigned',
            expect_success=True)

    def test_not_allow_unsigned(self):
        """Verify it fails to import an unsigned RPM to the repo.

        Importer configs:
            "allow_unsigned": False,
        """
        self._import_pkg_validate_result(
            repo_type='not_allow_unsigned',
            expect_success=False)

    def test_allow_unsigned_emp_allowed(self):
        """Verify it succeeds to import an unsigned RPM to the repo.

        Importer configs:
            "allow_keys": [],
            "allow_unsigned": True
        """
        self._import_pkg_validate_result(
            repo_type='allow_unsigned_empty_allowed',
            expect_success=True)
