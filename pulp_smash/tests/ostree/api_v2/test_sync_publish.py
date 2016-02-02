# coding=utf-8
"""Test the API endpoints `OSTree`_ `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an OSTree repo with feed (CreateTestCase).
    ├── When a valid feed and branch are given the repo syncs successfully
    │   without reporting errors (CreateValidFeedTestCase).
    └── When an invalid feed or branch is given, repo syncs fail and errors are
        reported (SyncInvalidFeedTestCase).

    It is possible to create a repository without a feed (CreateTestCase).
    └── Running sync on this repository fails with errors reported
        (SyncWithoutFeedTestCase).

.. _OSTree:
    http://pulp-ostree.readthedocs.org/en/latest/
.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import unittest2

from pulp_smash import api, config, utils
from pulp_smash.constants import REPOSITORY_PATH

_FEED = 'http://dl.fedoraproject.org/pub/fedora/linux/atomic/21/'
_BRANCHES = (
    'fedora-atomic/f21/x86_64/updates/docker-host',
    'fedora-atomic/f21/x86_64/updates-testing/docker-host',
)


def _gen_repo():
    """Return OSTree repo body."""
    return {
        'id': utils.uuid4(),
        'importer_type_id': 'ostree_web_importer',
        'importer_config': {},
        'distributors': [],
        'notes': {'_repo-type': 'OSTREE'},
    }


def _create_sync_repo(server_config, body):
    # Create repository.
    client = api.Client(server_config, api.json_handler)
    repo = client.post(REPOSITORY_PATH, body)

    # Sync repository and collect task statuses.
    client.response_handler = api.echo_handler
    response = client.post(
        urljoin(repo['_href'], 'actions/sync/'),
        {'override_config': {}},
    )
    response.raise_for_status()
    tasks = tuple(utils.poll_spawned_tasks(server_config, response.json()))
    return repo['_href'], response, tasks


class _BaseTestCase(unittest2.TestCase):
    """Provide a server config, and tear down created resources."""

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an iterable of resources to delete."""
        cls.cfg = config.get_config()
        cls.resources = set()

    @classmethod
    def tearDownClass(cls):
        """Delete created resources."""
        client = api.Client(cls.cfg)
        for resource in cls.resources:
            client.delete(resource)


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


class CreateTestCase(_BaseTestCase):
    """Create two OSTree repositories, with and without a feed."""

    @classmethod
    def setUpClass(cls):
        """Create two repositories."""
        super(CreateTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        cls.bodies = tuple((_gen_repo() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {'feed': utils.uuid4()}
        cls.repos = [client.post(REPOSITORY_PATH, body) for body in cls.bodies]
        cls.importers_iter = [
            client.get(urljoin(repo['_href'], 'importers/'))
            for repo in cls.repos
        ]
        for repo in cls.repos:
            cls.resources.add(repo['_href'])  # mark for deletion

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repository."""
        for body, repo in zip(self.bodies, self.repos):  # for input, output:
            for key in {'id', 'notes'}:
                with self.subTest(body=body):
                    self.assertIn(key, repo)
                    self.assertEqual(repo[key], body[key])

    def test_number_importers(self):
        """Assert each repository has one importer."""
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertEqual(len(importers), 1, importers)

    def test_importer_type_id(self):
        """Validate the ``importer_type_id`` attribute of each importer."""
        key = 'importer_type_id'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(importers[0][key], body[key])

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        key = 'config'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(importers[0][key], body['importer_' + key])


class SyncTestCase(_BaseTestCase):
    """Create an OSTree repository with a valid feed and branch, and sync it.

    The sync should complete with no errors reported.
    """

    @classmethod
    def setUpClass(cls):
        """Create an OSTree repository with a valid feed and branch."""
        super(SyncTestCase, cls).setUpClass()
        body = _gen_repo()
        body['importer_config']['feed'] = _FEED
        body['importer_config']['branches'] = [_BRANCHES[0]]
        repo_href, cls.report, cls.tasks = _create_sync_repo(cls.cfg, body)
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
        _BaseTestCase):
    """Create an OSTree repository with an invalid feed and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        body = _gen_repo()
        body['importer_config']['feed'] = utils.uuid4()
        body['importer_config']['branches'] = [_BRANCHES[0]]
        repo_href, cls.report, cls.tasks = _create_sync_repo(cls.cfg, body)
        cls.resources.add(repo_href)


class SyncInvalidBranchesTestCase(
        _SyncFailedMixin,
        _SyncImportFailedMixin,
        _BaseTestCase):
    """Create an OSTree repository with invalid branches and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncInvalidBranchesTestCase, cls).setUpClass()
        body = _gen_repo()
        body['importer_config']['feed'] = _FEED
        body['importer_config']['branches'] = [utils.uuid4()]
        repo_href, cls.report, cls.tasks = _create_sync_repo(cls.cfg, body)
        cls.resources.add(repo_href)


class SyncMissingAttrsTestCase(_SyncFailedMixin, _BaseTestCase):
    """Create an OSTree repository with no feed or branches and sync it."""

    @classmethod
    def setUpClass(cls):
        """Set ``cls.body``."""
        super(SyncMissingAttrsTestCase, cls).setUpClass()
        body = _gen_repo()
        repo_href, cls.report, cls.tasks = _create_sync_repo(cls.cfg, body)
        cls.resources.add(repo_href)
