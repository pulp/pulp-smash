# coding=utf-8
"""Test the API endpoints for RPM `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an RPM repo with a feed. (CreateTestCase)
    ├── If a valid feed is given, the sync completes and no errors are
    │   reported. (SyncValidFeedTestCase)
    └── If an invalid feed is given, the sync completes and errors are
        reported. (SyncInvalidFeedTestCase)

    It is possible to create an RPM repository without a feed. (CreateTestCase)
    └── It is possible to upload an RPM file to a repository, copy the
        repository's contents to a second repository, add a distributor to the
        first repository, publish the first repository, and download the
        original RPM. (PublishTestCase)

Assertions not explored in this module include:

* Given an RPM repository without a feed, sync requests fail.
* It is impossible to create two RPM repositories with the same relative URL.
* It is possible to upload a directory of RPM files to an RPM repository.
* It is possible to upload an ISO of RPM files to an RPM repository.
* It is possible to upload content and copy it into multiple repositories.
* It is possible to get content into a repository via a sync and publish it.

.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from __future__ import unicode_literals

import hashlib
from itertools import product
try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import unittest2
from packaging.version import Version

from pulp_smash import api, selectors, utils
from pulp_smash.constants import (
    CALL_REPORT_KEYS,
    CONTENT_UPLOAD_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
    RPM_SHA256_CHECKSUM,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo


_REPO_PUBLISH_PATH = '/pulp/repos/'  # + relative_url + unit_name.rpm.arch


class CreateTestCase(utils.BaseAPITestCase):
    """Create two RPM repositories, with and without feed URLs respectively."""

    @classmethod
    def setUpClass(cls):
        """Create two RPM repositories, with and without feed URLs."""
        super(CreateTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        cls.bodies = tuple((gen_repo() for _ in range(2)))
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
                self.assertEqual(len(importers), 1)

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


class SyncValidFeedTestCase(utils.BaseAPITestCase):
    """Create an RPM repository with a valid feed and sync it.

    The sync should complete with no errors reported.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repo with a valid feed, sync it, and read the repo."""
        super(SyncValidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        client.response_handler = api.echo_handler
        path = urljoin(repo['_href'], 'actions/sync/')
        cls.report = client.post(path, {'override_config': {}})
        cls.report.raise_for_status()
        cls.tasks = tuple(api.poll_spawned_tasks(cls.cfg, cls.report.json()))
        client.response_handler = api.json_handler
        cls.repo = client.get(repo['_href'])
        cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_error_traceback(self):
        """Assert each task's "error" and "traceback" fields are null."""
        if (self.cfg.version >= Version('2.8') and
                selectors.bug_is_untestable(1455)):
            self.skipTest('https://pulp.plan.io/issues/1455')
        for i, task in enumerate(self.tasks):
            for key in {'error', 'traceback'}:
                with self.subTest((i, key)):
                    self.assertIsNone(task[key])

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        for i, task in enumerate(self.tasks):
            with self.subTest(i=i):
                self.assertEqual(
                    task['progress_report']['yum_importer']['content']['error_details'],  # noqa pylint:disable=line-too-long
                    []
                )

    def test_unit_count_on_repo(self):
        """Verify that the sync added the correct number of units to the repo.

        Read the repository and examine its ``content_unit_counts`` attribute.
        Compare these attributes to metadata from the remote repository.
        Expected values are currently hard-coded into this test.
        """
        if (self.cfg.version >= Version('2.8') and
                selectors.bug_is_untestable(1455)):
            self.skipTest('https://pulp.plan.io/issues/1455')
        counts = self.repo.get('content_unit_counts', {})
        for unit_type, count in {
                'rpm': 32,
                'erratum': 4,
                'package_group': 2,
                'package_category': 1,
        }.items():
            if (unit_type == 'rpm' and self.cfg.version >= Version('2.8') and
                    selectors.bug_is_untestable(1570)):
                continue
            with self.subTest(unit_type=unit_type):
                self.assertEqual(counts.get(unit_type), count)


class SyncInvalidFeedTestCase(utils.BaseAPITestCase):
    """Create an RPM repository with an invalid feed and sync it.

    The sync should complete with errors reported.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with an invalid feed and sync it."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = utils.uuid4()
        repo = client.post(REPOSITORY_PATH, body)
        client.response_handler = api.echo_handler
        path = urljoin(repo['_href'], 'actions/sync/')
        cls.report = client.post(path, {'override_config': {}})
        cls.report.raise_for_status()
        cls.tasks = tuple(api.poll_spawned_tasks(cls.cfg, cls.report.json()))
        cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_error_traceback(self):
        """Assert each task's "error" and "traceback" fields are non-null."""
        if (self.cfg.version >= Version('2.8') and
                selectors.bug_is_untestable(1455)):
            self.skipTest('https://pulp.plan.io/issues/1455')
        for i, task in enumerate(self.tasks):
            for key in {'error', 'traceback'}:
                with self.subTest((i, key)):
                    self.assertIsNotNone(task[key])

    def test_task_progress_report(self):
        """Assert each task's progress report contains error details."""
        self.skipTest('https://pulp.plan.io/issues/1376')
        for i, task in enumerate(self.tasks):
            with self.subTest(i=i):
                self.assertNotEqual(
                    task['progress_report']['yum_importer']['content']['error_details'],  # noqa pylint:disable=line-too-long
                    []
                )

    def test_number_tasks(self):
        """Assert that only one task was spawned."""
        self.assertEqual(len(self.tasks), 1)


class PublishTestCase(utils.BaseAPITestCase):
    """Upload an RPM to a repo, copy it to another, publish, and download."""

    @classmethod
    def setUpClass(cls):
        """Test RPM uploading and downloading, and repo syncing and publishing.

        Do the following:

        1. Create two RPM repositories, both without feeds.
        2. Upload an RPM to the first repository.
        3. Associate the first repository with the second, causing the RPM to
           be copied.
        4. Add a distributor to both repositories, publish them, and download
           RPMs from both repositories.
        """
        super(PublishTestCase, cls).setUpClass()
        utils.reset_pulp(cls.cfg)  # See: https://pulp.plan.io/issues/1406
        cls.responses = {}
        cls.rpms = []  # Raw RPMs

        # Download an RPM and create two repositories.
        client = api.Client(cls.cfg, api.json_handler)
        repos = [client.post(REPOSITORY_PATH, gen_repo()) for _ in range(2)]
        for repo in repos:
            cls.resources.add(repo['_href'])
        client.response_handler = api.safe_handler
        cls.rpms.append(client.get(urljoin(RPM_FEED_URL, RPM)).content)

        # Begin an upload request, upload an RPM, move the RPM into a
        # repository, and end the upload request.
        cls.responses['malloc'] = client.post(CONTENT_UPLOAD_PATH)
        cls.responses['upload'] = client.put(
            urljoin(cls.responses['malloc'].json()['_href'], '0/'),
            data=cls.rpms[0],
        )
        cls.responses['import'] = client.post(
            urljoin(repos[0]['_href'], 'actions/import_upload/'),
            {
                'unit_key': {},
                'unit_type_id': 'rpm',
                'upload_id': cls.responses['malloc'].json()['upload_id'],
            },
        )
        cls.responses['free'] = client.delete(
            cls.responses['malloc'].json()['_href'],
        )

        # Copy content from the first repository to the second.
        cls.responses['copy'] = client.post(
            urljoin(repos[1]['_href'], 'actions/associate/'),
            {'source_repo_id': repos[0]['id']}
        )

        # Add a distributor to and publish both repositories.
        cls.responses['distribute'] = []
        cls.responses['publish'] = []
        for repo in repos:
            cls.responses['distribute'].append(client.post(
                urljoin(repo['_href'], 'distributors/'),
                gen_distributor(),
            ))
            cls.responses['publish'].append(client.post(
                urljoin(repo['_href'], 'actions/publish/'),
                {'id': cls.responses['distribute'][-1].json()['id']},
            ))

        # Download the RPM from both repositories.
        for response in cls.responses['distribute']:
            url = urljoin(
                '/pulp/repos/',
                response.json()['config']['relative_url']
            )
            url = urljoin(url, RPM)
            cls.rpms.append(client.get(url).content)

        # Search for all units in each of the two repositories.
        body = {'criteria': {}}
        cls.responses['repo units'] = [
            client.post(urljoin(repo['_href'], 'search/units/'), body)
            for repo in repos
        ]

    def test_status_code(self):
        """Verify the HTTP status code of each server response."""
        for step, code in (
                ('malloc', 201),
                ('upload', 200),
                ('import', 202),
                ('free', 200),
                ('copy', 202),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)
        for step, code in (
                ('distribute', 201),
                ('publish', 202),
                ('repo units', 200),
        ):
            with self.subTest(step=step):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_malloc(self):
        """Verify the response body for `creating an upload request`_.

        .. _creating an upload request:
           http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/upload.html#creating-an-upload-request
        """
        keys = set(self.responses['malloc'].json().keys())
        self.assertLessEqual({'_href', 'upload_id'}, keys)

    def test_upload(self):
        """Verify the response body for `uploading bits`_.

        .. _uploading bits:
           http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/upload.html#upload-bits
        """
        self.assertIsNone(self.responses['upload'].json())

    def test_call_report_keys(self):
        """Verify each call report has a sane structure.

        * `Import into a Repository
          <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/upload.html#import-into-a-repository>`_
        * `Copying Units Between Repositories
          <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/associate.html#copying-units-between-repositories>`_
        """
        for step in {'import', 'copy'}:
            with self.subTest(step=step):
                keys = frozenset(self.responses[step].json().keys())
                self.assertLessEqual(CALL_REPORT_KEYS, keys)

    def test_call_report_errors(self):
        """Verify each call report is error-free."""
        for step, key in product({'import', 'copy'}, {'error', 'result'}):
            with self.subTest((step, key)):
                self.assertIsNone(self.responses[step].json()[key])

    def test_free(self):
        """Verify the response body for ending an upload.

        `Delete an Upload Request
        <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/upload.html#delete-an-upload-request>`_
        """
        self.assertIsNone(self.responses['free'].json())

    def test_publish_keys(self):
        """Verify publishing a repository generates a call report."""
        for i, response in enumerate(self.responses['publish']):
            with self.subTest(i=i):
                keys = frozenset(response.json().keys())
                self.assertLessEqual(CALL_REPORT_KEYS, keys)

    def test_publish_errors(self):
        """Verify publishing a call report doesn't generate any errors."""
        for i, response in enumerate(self.responses['publish']):
            for key in {'error', 'result'}:
                with self.subTest((i, key)):
                    self.assertIsNone(response.json()[key])

    def test_repo_units_consistency(self):
        """Verify the two repositories have the same content units."""
        bodies = [resp.json() for resp in self.responses['repo units']]
        self.assertEqual(
            set(unit['unit_id'] for unit in bodies[0]),  # This test is fragile
            set(unit['unit_id'] for unit in bodies[1]),  # due to hard-coded
        )  # indices. But the data is complex, and this makes things simpler.

    def test_unit_integrity(self):
        """Verify the integrity of the RPMs downloaded from Pulp."""
        # First module is downloaded from external source, others from Pulp.
        for i, module in enumerate(self.rpms[1:]):
            with self.subTest(i=i):
                self.assertEqual(self.rpms[0], module)


class SyncOnDemandTestCase(utils.BaseAPITestCase):
    """Assert the RPM plugin supports on-demand syncing of yum repositories.

    Beware that this test case will fail if Pulp's Squid server is not
    configured to return an appropriate hostname or IP when performing
    redirection.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a valid feed and sync it.

        Do the following:

        1. Reset Pulp, including the Squid cache.
        2. Create a repository. Sync and publish it using the 'on_demand'
           download policy.
        3. Download an RPM from the published repository.
        4. Download the same RPM to ensure it is served by the cache.
        """
        super(SyncOnDemandTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('This test requires Pulp 2.8 or greater.')

        # Ensure `locally_stored_units` is 0 before we start.
        utils.reset_squid(cls.cfg)
        utils.reset_pulp(cls.cfg)

        # Create a repository
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'download_policy': 'on_demand',
            'feed': RPM_FEED_URL,
        }
        distributor = gen_distributor()
        distributor['auto_publish'] = True
        distributor['distributor_config']['relative_url'] = body['id']
        body['distributors'] = [distributor]

        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Sync and read the repository
        sync_path = urljoin(repo['_href'], 'actions/sync/')
        client.post(sync_path, {'override_config': {}})
        cls.repo = client.get(repo['_href'], params={'details': True})

        # Download the same RPM twice.
        client.response_handler = api.safe_handler
        path = urljoin('/pulp/repos/', repo['id'] + '/')
        path = urljoin(path, RPM)
        cls.rpm = client.get(path)
        cls.same_rpm = client.get(path)

    def test_local_units(self):
        """Assert no content units were downloaded besides metadata."""
        metadata_unit_count = sum([
            count for name, count in self.repo['content_unit_counts'].items()
            if name not in ('rpm', 'drpm', 'srpm')
        ])
        self.assertEqual(
            self.repo['locally_stored_units'],
            metadata_unit_count
        )

    def test_repository_units(self):
        """Assert there is at least one content unit in the repository."""
        total_units = sum(self.repo['content_unit_counts'].values())
        self.assertEqual(self.repo['total_repository_units'], total_units)

    def test_request_history(self):
        """Assert the initial request received a 302 Redirect."""
        self.assertTrue(self.rpm.history[0].is_redirect)

    def test_rpm_checksum(self):
        """Assert the checksum of the downloaded RPM matches the metadata."""
        checksum = hashlib.sha256(self.rpm.content).hexdigest()
        self.assertEqual(RPM_SHA256_CHECKSUM, checksum)

    def test_rpm_cache_lookup_header(self):
        """Assert the first request resulted in a cache miss from Squid."""
        self.assertIn('MISS', self.rpm.headers['X-Cache-Lookup'])

    def test_rpm_cache_control_header(self):
        """Assert the request has the Cache-Control header set."""
        self.assertEqual(
            {'s-maxage=86400', 'public', 'max-age=86400'},
            set(self.rpm.headers['Cache-Control'].split(', '))
        )

    def test_same_rpm_checksum(self):
        """Assert the checksum of the second RPM matches the metadata."""
        checksum = hashlib.sha256(self.same_rpm.content).hexdigest()
        self.assertEqual(RPM_SHA256_CHECKSUM, checksum)

    def test_same_rpm_cache_header(self):
        """Assert the second request resulted in a cache hit from Squid."""
        self.assertIn('HIT', self.same_rpm.headers['X-Cache-Lookup'])
