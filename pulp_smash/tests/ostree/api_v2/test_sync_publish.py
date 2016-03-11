# coding=utf-8
"""Test the API endpoints `OSTree`_ `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
`pulp_smash.tests.ostree.api_v2.test_crud` hold true. The following trees of
assumptions are explored in this module::

    It is possible to create an OSTree repo with feed (test_crud).
    ├── When a valid feed and branch are given the repo syncs successfully
    │   without reporting errors (CreateValidFeedTestCase).
    └── When an invalid feed or branch is given, repo syncs fail and errors are
        reported (SyncInvalidFeedTestCase).

    It is possible to create a repository without a feed (test_crud).
    └── Running sync on this repository fails with errors reported
        (SyncWithoutFeedTestCase).

.. _OSTree:
    http://pulp-ostree.readthedocs.org/en/latest/
.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from __future__ import unicode_literals

from pulp_smash import utils
from pulp_smash.tests.ostree import ostree_utils

_FEED = 'https://repos.fedorapeople.org/pulp/pulp/demo_repos/test-ostree-small'
_BRANCHES = (
    'fedora-atomic/f21/x86_64/updates/docker-host',
    'fedora-atomic/f21/x86_64/updates-testing/docker-host',
)


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests if the OSTree plugin is not installed."""
    ostree_utils.setUpModule()


class _SyncFailedMixin(object):
    """Add test methods verifying Pulp's behaviour when a sync fails.

    This mixin assumes that:

    * The ``report`` and ``tasks`` instance attributes are available. The
      former should be the response to a "sync repository" API call — a call
      report. The latter should be a collection of completed task states.
    * The child class making use of this mixin is a unittest-compatible test
      case.
    """

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_number_tasks(self):
        """Assert that exactly one task was spawned."""
        self.assertEqual(len(self.tasks), 1, self.tasks)

    def test_task_error_traceback(self):
        """Assert each task's "error" and "traceback" fields are non-null."""
        for i, task in enumerate(self.tasks):
            for key in {'error', 'traceback'}:
                with self.subTest((i, key)):
                    self.assertIsNotNone(task[key])


# It's OK for a mixin to have just one method.
class _SyncImportFailedMixin(object):  # pylint:disable=too-few-public-methods
    """Add test methods verifying Pulp's behaviour when a sync fails.

    This class is like ``_SyncFailedMixin``, with the additional restriction
    that the repo being synced is an OSTree repo with a feed and/or branches.
    """

    def test_error_details(self):
        """Assert that some task's progress report contains error details."""
        for task in self.tasks:
            num_error_details = sum(
                1 if action['error_details'] != [] else 0
                for action in task['progress_report']['ostree_web_importer']
            )
            self.assertGreater(num_error_details, 0)


class SyncTestCase(utils.BaseAPITestCase):
    """Create an OSTree repository with a valid feed and branch, and sync it.

    The sync should complete with no errors reported.
    """

    @classmethod
    def setUpClass(cls):
        """Create an OSTree repository with a valid feed and branch."""
        super(SyncTestCase, cls).setUpClass()
        body = ostree_utils.gen_repo()
        body['importer_config']['feed'] = _FEED
        body['importer_config']['branches'] = [_BRANCHES[0]]
        repo_href, cls.report, cls.tasks = ostree_utils.create_sync_repo(
            cls.cfg, body
        )
        cls.resources.add(repo_href)

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_error_traceback(self):
        """Assert each task's "error" and "traceback" fields are null."""
        for i, task in enumerate(self.tasks):
            for key in {'error', 'traceback'}:
                with self.subTest((i, key)):
                    self.assertIsNone(task[key])

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        for task in self.tasks:
            for action in task['progress_report']['ostree_web_importer']:
                with self.subTest(task=task):
                    self.assertEqual(action['error_details'], [])


class SyncInvalidFeedTestCase(
        _SyncFailedMixin,
        _SyncImportFailedMixin,
        utils.BaseAPITestCase):
    """Create an OSTree repository with an invalid feed and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        body = ostree_utils.gen_repo()
        body['importer_config']['feed'] = utils.uuid4()
        body['importer_config']['branches'] = [_BRANCHES[0]]
        repo_href, cls.report, cls.tasks = ostree_utils.create_sync_repo(
            cls.cfg, body
        )
        cls.resources.add(repo_href)


class SyncInvalidBranchesTestCase(
        _SyncFailedMixin,
        _SyncImportFailedMixin,
        utils.BaseAPITestCase):
    """Create an OSTree repository with invalid branches and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncInvalidBranchesTestCase, cls).setUpClass()
        body = ostree_utils.gen_repo()
        body['importer_config']['feed'] = _FEED
        body['importer_config']['branches'] = [utils.uuid4()]
        repo_href, cls.report, cls.tasks = ostree_utils.create_sync_repo(
            cls.cfg, body
        )
        cls.resources.add(repo_href)


class SyncMissingAttrsTestCase(_SyncFailedMixin, utils.BaseAPITestCase):
    """Create an OSTree repository with no feed or branches and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncMissingAttrsTestCase, cls).setUpClass()
        body = ostree_utils.gen_repo()
        repo_href, cls.report, cls.tasks = ostree_utils.create_sync_repo(
            cls.cfg, body
        )
        cls.resources.add(repo_href)
