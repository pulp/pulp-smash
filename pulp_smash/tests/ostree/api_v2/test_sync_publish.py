# coding=utf-8
"""Test the API endpoints `OSTree`_ `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an OSTree repo with feed (CreateTestCase).
    ├── When valid feed and branch are given repo synces successfully without
    │   reported errors (CreateValidFeedTestCase).
    ├── When Invalid feed or branch is given repo sync fails with errors
    │   reported (SyncInvalidFeedTestCase).
    └── It is possible to sync repository, copy its content to a second
        repository, update repository metadata, sync again, add distributor
        to the first repository and publish it and access published content
        (PublishTestCase).

    It is possible to create repository without feed (CreateTestCase).
    └── Running sync on this repository fails with errors reported
        (SyncWithoutFeedTestCase).

.. _OSTree:
    http://pulp-ostree.readthedocs.org/en/latest/
.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from __future__ import unicode_literals

from itertools import chain
from urlparse import urljoin
from unittest2 import TestCase
from packaging.version import Version

from pulp_smash import api, utils, selectors
from pulp_smash.config import get_config
from pulp_smash.constants import REPOSITORY_PATH

_VALID_FEED = 'http://dl.fedoraproject.org/pub/fedora/linux/atomic/21/'
_VALID_BRANCHES = tuple((
    'fedora-atomic/f21/x86_64/updates/docker-host',
    'fedora-atomic/f21/x86_64/updates-testing/docker-host',
))


class _BaseTestCase(TestCase):
    """Provide a server config, and tear down created resources."""

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an iterable of resources to delete."""
        cls.cfg = get_config()
        cls.resources = set()

    @classmethod
    def tearDownClass(cls):
        """Delete created resources."""
        client = api.Client(cls.cfg)
        for resource in cls.resources:
            client.delete(resource)


def _gen_ostree_repo_body():
    """Return OSTree repo body."""
    return {
        'id': utils.uuid4(),
        'importer_type_id': 'ostree_web_importer',
        'importer_config': {},
        'distributors': [],
        'notes': {'_repo-type': 'OSTREE'},
    }


class CreateTestCase(_BaseTestCase):
    """Create two OSTree repositories, with and without feed."""

    @classmethod
    def setUpClass(cls):
        """Create two repositories."""
        super(CreateTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        cls.bodies = tuple((_gen_ostree_repo_body() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {'feed': utils.uuid4()}
        cls.repos = [client.post(REPOSITORY_PATH, body) for body in cls.bodies]
        cls.importers_iter = [
            client.get(urljoin(repo['_href'], 'importers/'))
            for repo in cls.repos
        ]
        for repo in cls.repos:
            cls.resources.add(repo['_href'])  # mark for deletion

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repo."""
        for key in ('id', 'notes'):
            for body, attrs in zip(self.bodies, self.repos):
                with self.subTest((key, body, attrs)):
                    self.assertIn(key, attrs)
                    self.assertEqual(body[key], attrs[key])

    def test_number_importers(self):
        """Each repository should have only one importer."""
        for i, importers in enumerate(self.importers_iter):
            with self.subTest(i=i):
                self.assertEqual(len(importers), 1, importers)

    def test_importer_type_id(self):
        """Validate the ``importer_type_id`` attribute of each importer."""
        key = 'importer_type_id'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest((body, importers)):
                self.assertIn(key, importers[0])
                self.assertEqual(body[key], importers[0][key])

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        key = 'config'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest((body, importers)):
                self.assertIn(key, importers[0])
                self.assertEqual(body['importer_' + key], importers[0][key])


class SyncValidFeedTestCase(_BaseTestCase):
    """With a valid feed given, the sync completes with no reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create an OSTree repository with a valid feed and branch."""
        super(SyncValidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = _gen_ostree_repo_body()
        body['importer_config']['feed'] = _VALID_FEED
        body['importer_config']['branches'] = [_VALID_BRANCHES[0]]
        repo = client.post(REPOSITORY_PATH, body)
        client.response_handler = api.safe_handler
        cls.sync_report = client.post(
            urljoin(repo['_href'], 'actions/sync/'),
            {'override_config': {}}
        )
        cls.task_bodies = tuple(
            utils.poll_spawned_tasks(cls.cfg, cls.sync_report.json())
        )
        client.response_handler = api.json_handler
        cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.sync_report.status_code, 202)

    def test_task_error(self):
        """Assert each task's "error" field is null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertIsNone(task_body['error'])

    def test_task_traceback(self):
        """Assert each task's "traceback" field is null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertIsNone(task_body['traceback'])

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        for i, task_body in enumerate(self.task_bodies):
            for action in task_body['progress_report']['ostree_web_importer']:
                with self.subTest(i=i):
                    self.assertEqual(
                        len(action['error_details']),
                        0,
                        task_body
                    )


class SyncWithoutFeedTestCase(_BaseTestCase):
    """Without provided feed, repo synchronisation fails."""

    @classmethod
    def setUpClass(cls):
        """Create repository without feed and run sync on it."""
        super(SyncWithoutFeedTestCase, cls).setUpClass()
        body = _gen_ostree_repo_body()
        client = api.Client(cls.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, body)
        client.response_handler = api.safe_handler
        cls.sync_report = client.post(
            urljoin(repo['_href'], 'actions/sync/'),
            {'override_config': {}}
        )
        cls.task_bodies = tuple(
            utils.poll_spawned_tasks(cls.cfg, cls.sync_report.json())
        )
        client.response_handler = api.json_handler
        cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.sync_report.status_code, 202)

    def test_task_error(self):
        """Assert each task's "error" field is non-null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertIsNotNone(task_body['error'])

    def test_task_traceback(self):
        """Assert each task's "traceback" field is non-null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertIsNotNone(task_body['traceback'])

    def test_number_tasks(self):
        """Assert that two task were spawned."""
        self.assertEqual(len(self.task_bodies), 1)


class SyncInvalidFeedTestCase(_BaseTestCase):
    """With invalid feed or branch, the sync completes with reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create an OSTree repository with an invalid feed or branch, sync."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        bodies = tuple(_gen_ostree_repo_body() for _ in range(2))
        bodies[0]['importer_config']['feed'] = utils.uuid4()  # invalid feed
        bodies[0]['importer_config']['branches'] = [_VALID_BRANCHES[0]]
        bodies[1]['importer_config']['feed'] = _VALID_FEED
        bodies[1]['importer_config']['branches'] = [utils.uuid4()]
        repos = tuple(client.post(REPOSITORY_PATH, body) for body in bodies)
        client.response_handler = api.safe_handler
        cls.sync_reports = [
            client.post(
                urljoin(repo['_href'], 'actions/sync/'),
                {'override_config': {}}) for repo in repos
            ]
        cls.task_bodies = tuple(chain.from_iterable(
            utils.poll_spawned_tasks(cls.cfg, report.json())
            for report in cls.sync_reports
        ))
        for repo in repos:
            cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        for sync_repo in self.sync_reports:
            with self.subTest(sync_repo=sync_repo):
                self.assertEqual(sync_repo.status_code, 202)

    def test_task_error(self):
        """Assert each task's "error" field is non-null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertIsNotNone(task_body['error'])

    def test_task_traceback(self):
        """Assert each task's "traceback" field is non-null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertIsNotNone(task_body['traceback'])

    def test_error_details(self):
        """Assert that some task's progress report contains error details."""
        for task_body in self.task_bodies:
            error_details_num = 0
            for action in task_body['progress_report']['ostree_web_importer']:
                if action['error_details'] != []:
                    error_details_num += 1
            self.assertNotEqual(error_details_num, 0)

    def test_number_tasks(self):
        """Assert that two task were spawned."""
        self.assertEqual(len(self.task_bodies), 2)


class PublishTestCase(_BaseTestCase):
    """Create two repositories, one with feed.

    Sync, copy first repository to the second, update branch on first and
    publish it. Download and compare units.

    """
    @classmethod
    def setUpClass(cls):
        """Create an OSTree repository with a valid feed and sync it.

        Create two repos, one with feed. Sync one, copy to another, publish,
        check that units match.
        """
        super(PublishTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)

        steps = {
            'update',
            'sync',
            'copy',
            'distribute',
            'publish',
            'search units',
        }
        cls.responses = {key: [] for key in steps}
        cls.bodies = {}
        cls.task_bodies = {key: [] for key in {'sync', 'copy'}}

        bodies = tuple(_gen_ostree_repo_body() for _ in range(2))
        bodies[0]['importer_config']['feed'] = _VALID_FEED
        bodies[0]['importer_config']['branches'] = [_VALID_BRANCHES[0]]
        repos = tuple(client.post(REPOSITORY_PATH, body) for body in bodies)
        client.response_handler = api.safe_handler
        # sync first repo with first branch
        cls.responses['sync'].append(client.post(
            urljoin(repos[0]['_href'], 'actions/sync/'),
            {'override_config': {}}
        ))
        cls.task_bodies['sync'] += list(tuple(utils.poll_spawned_tasks(
            cls.cfg, cls.responses['sync'][-1].json())))

        # copy content from repo #0 to repo #1
        cls.responses['copy'].append(client.post(
            urljoin(repos[1]['_href'], 'actions/associate/'),
            {'source_repo_id': repos[0]['id']}
        ))
        cls.task_bodies['copy'] += list(tuple(utils.poll_spawned_tasks(
            cls.cfg, cls.responses['copy'][-1].json())))

        # update branch of first repository
        cls.responses['update'].append(client.put(
            urljoin(cls.cfg.base_url, repos[0]['_href']),
            {'importer_config': {'branches': [_VALID_BRANCHES[1]]},
             'delta': {'bg': False}},
        ))
        # sync with new branch
        cls.responses['sync'].append(client.post(
            urljoin(repos[0]['_href'], 'actions/sync/'),
            {'override_config': {}}
        ))
        cls.task_bodies['sync'] += tuple(utils.poll_spawned_tasks(
            cls.cfg, cls.responses['sync'][-1].json()))

        # add distributor to first repository and publish
        cls.responses['distribute'].append(client.post(
            urljoin(cls.cfg.base_url, repos[0]['_href'] + 'distributors/'),
            {
                'auto_publish': False,
                'distributor_id': utils.uuid4(),
                'distributor_type_id': 'ostree_web_distributor',
                'distributor_config': {'relative_path': '/' + utils.uuid4(), },
            }
        ))
        cls.responses['publish'].append(client.post(
            urljoin(repos[0]['_href'], 'actions/publish/'),
            {'id': cls.responses['distribute'][-1].json()['id']}
        ))
        tuple(utils.poll_spawned_tasks(
            cls.cfg, cls.responses['publish'][-1].json()))

        # search for content in both repositories
        cls.responses['search units'] += tuple(client.post(
            urljoin(repo['_href'], 'search/units/'),
            {'criteria': {}}) for repo in repos)

        cls.units = []
        cls.original_units = []
        # download files from server over https
        if (cls.cfg.version >= Version('2.8') and
                selectors.bug_is_untestable(1609)):
            for branch in _VALID_BRANCHES:
                for distributor in cls.responses['distribute']:
                    url = urljoin(
                        cls.cfg.base_url,
                        'pulp/ostree/web/' +
                        distributor.json()['config']['relative_path'] +
                        '/refs/heads/' +
                        branch)
                    response = client.get(url)
                    cls.units.append(response.content)
                    url_orig = urljoin(_VALID_FEED, 'refs/heads/' + branch)
                    response = client.get(url_orig)
                    cls.original_units.append(response.content)
                    cls.original_units[-1] = cls.original_units[-1].replace('\n', '')  # noqa pylint:disable=line-too-long

        for repo in repos:
            cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert that all HTTP calls return without any error."""
        steps_codes = (
            ('update', 200),
            ('sync', 202),
            ('distribute', 201),
            ('publish', 202),
            ('copy', 202),
            ('search units', 200),
        )
        for step, code in steps_codes:
            with self.subTest((step, code)):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_task_error(self):
        """Assert each task's "error" field is null."""
        for step in {'sync', 'copy'}:
            for i, task_body in enumerate(self.task_bodies[step]):
                with self.subTest(i=i):
                    self.assertEqual(task_body['error'], None)

    def test_task_traceback(self):
        """Assert each task's "traceback" field is null."""
        for step in {'sync', 'copy'}:
            for i, task_body in enumerate(self.task_bodies[step]):
                with self.subTest(i=i):
                    self.assertEqual(task_body['traceback'], None)

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        for i, task_body in enumerate(self.task_bodies['sync']):
            for action in task_body['progress_report']['ostree_web_importer']:
                with self.subTest(i=i):
                    self.assertEqual(
                        len(action['error_details']),
                        0)

    def test_search_units(self):
        """Verify that the content of two repositories differ."""
        repo0set = set(unit['unit_id']
                       for unit in self.responses['search units'][0].json())
        repo1set = set(unit['unit_id']
                       for unit in self.responses['search units'][1].json())
        with self.subTest(repo0set=repo0set):
            self.assertEqual(len(repo0set), 2)
        with self.subTest(repo1set=repo1set):
            self.assertEqual(len(repo1set), 1)
        with self.subTest():
            self.assertTrue(repo1set.issubset(repo0set))

    def test_units_published(self):
        """Assert that the original units and synced ones are equal."""
        if (self.cfg.version >= Version('2.8') and
                selectors.bug_is_untestable(1609)):
            self.skipTest('https://pulp.plan.io/issues/1609')
        for unit, orig_unit in zip(self.units, self.original_units):
            with self.subTest(unit=unit):
                self.assertEqual(unit, orig_unit)
