# coding=utf-8
"""Tests that sync `OSTree`_ `repositories`_.

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
    http://docs.pulpproject.org/plugins/pulp_ostree/
.. _repositories:
   http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, selectors, utils
from pulp_smash.constants import OSTREE_FEED, OSTREE_BRANCH, REPOSITORY_PATH
from pulp_smash.tests.ostree.utils import gen_repo
from pulp_smash.tests.ostree.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _sync_repo(server_config, href):
    """Sync a repository and wait for the sync to complete.

    Verify only the call report's status code. Do not verify each individual
    task, as the default response handler does. Return ``call_report, tasks``.
    """
    response = api.Client(server_config, api.echo_handler).post(
        urljoin(href, 'actions/sync/'),
        {'override_config': {}},
    )
    response.raise_for_status()
    tasks = tuple(api.poll_spawned_tasks(server_config, response.json()))
    return response, tasks


# It's OK for a mixin to have just one method.
class _SyncMixin(object):  # pylint:disable=too-few-public-methods
    """Add test methods verifying Pulp's behaviour when a sync is started.

    The ``report`` instance attribute should be available. This is the response
    to a "sync repository" API call: a call report.
    """

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)


class _SyncFailedMixin(object):
    """Add test methods verifying Pulp's behaviour when a sync fails.

    This mixin assumes that:

    * The ``report`` and ``tasks`` instance attributes are available. The
      former should be the response to a "sync repository" API call — a call
      report. The latter should be a collection of completed task states.
    * The child class making use of this mixin is a unittest-compatible test
      case.
    """

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
        """Assert that each task's progress report contains error details."""
        for task in self.tasks:
            num_error_details = sum(
                1 if action['error_details'] != [] else 0
                for action in task['progress_report']['ostree_web_importer']
            )
            self.assertGreater(num_error_details, 0)


class SyncTestCase(_SyncMixin, utils.BaseAPITestCase):
    """Create an OSTree repository with a valid feed and branch, and sync it.

    The sync should complete with no errors reported.
    """

    @classmethod
    def setUpClass(cls):
        """Create an OSTree repository with a valid feed and branch."""
        super(SyncTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1934, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1934')
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED
        body['importer_config']['branches'] = [OSTREE_BRANCH]
        repo = api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])
        cls.report = utils.sync_repo(cls.cfg, repo)
        cls.tasks = tuple(api.poll_spawned_tasks(cls.cfg, cls.report.json()))

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        for task in self.tasks:
            for action in task['progress_report']['ostree_web_importer']:
                with self.subTest(task=task):
                    self.assertEqual(action['error_details'], [])


class SyncInvalidFeedTestCase(
        _SyncMixin,
        _SyncFailedMixin,
        _SyncImportFailedMixin,
        utils.BaseAPITestCase):
    """Create an OSTree repository with an invalid feed and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = utils.uuid4()
        body['importer_config']['branches'] = [OSTREE_BRANCH]
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(repo_href)
        cls.report, cls.tasks = _sync_repo(cls.cfg, repo_href)


class SyncInvalidBranchesTestCase(
        _SyncMixin,
        _SyncFailedMixin,
        _SyncImportFailedMixin,
        utils.BaseAPITestCase):
    """Create an OSTree repository with invalid branches and sync it."""

    @classmethod
    def setUpClass(cls):
        """Create and sync an OSTree repository."""
        super(SyncInvalidBranchesTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED
        body['importer_config']['branches'] = [utils.uuid4()]
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(repo_href)
        cls.report, cls.tasks = _sync_repo(cls.cfg, repo_href)


class SyncMissingAttrsTestCase(
        _SyncMixin,
        _SyncFailedMixin,
        utils.BaseAPITestCase):
    """Create an OSTree repository with no feed or branches and sync it."""

    @classmethod
    def setUpClass(cls):
        """Create and sync an OSTree repository."""
        super(SyncMissingAttrsTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        body = gen_repo()
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(repo_href)
        cls.report, cls.tasks = _sync_repo(cls.cfg, repo_href)
