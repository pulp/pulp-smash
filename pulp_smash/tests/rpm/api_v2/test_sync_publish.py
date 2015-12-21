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

import os
import requests
from pulp_smash.config import get_config
from pulp_smash.constants import CALL_REPORT_KEYS
from pulp_smash.utils import (
    create_repository,
    delete,
    get,
    get_importers,
    handle_response,
    poll_spawned_tasks,
    publish_repository,
    sync_repository,
    uuid4,
)
from unittest2 import TestCase


from sys import version_info
if version_info.major == 2:
    from urlparse import urlparse  # noqa pylint:disable=import-error,no-name-in-module
else:
    from urllib.parse import urlparse  # noqa pylint:disable=import-error,no-name-in-module


_VALID_FEED = 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/zoo/'
_INVALID_FEED = 'https://example.com'
_RPM_URL = (
    'https://repos.fedorapeople.org'
    '/pulp/pulp/demo_repos/zoo/bear-4.1-1.noarch.rpm'
)
_REPO_PUBLISH_PATH = '/pulp/repos/'  # + relative_url + unit_name.rpm.arch
_CONTENT_UPLOADS_PATH = '/pulp/api/v2/content/uploads/'


def _get_units(server_config, href, responses=None):
    """Search for a repository's units."""
    return handle_response(requests.post(
        server_config.base_url + href + 'search/units/',
        json={'criteria': {}},
        **server_config.get_requests_kwargs()
    ), responses)


def _start_content_upload(server_config, responses=None):
    """Start a content upload.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.
    """
    return handle_response(requests.post(
        server_config.base_url + _CONTENT_UPLOADS_PATH,
        **server_config.get_requests_kwargs()
    ), responses)


def _upload_file(server_config, href, content, responses=None):
    """Upload a file and return the server's response.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to an open upload request.
    :param content: The content of the file to upload.
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.
    """
    return handle_response(requests.put(
        server_config.base_url + href + '0/',
        data=content,
        **server_config.get_requests_kwargs()
    ), responses)


def _import_rpm_to_repo(server_config, upload_id, href, responses=None):
    """Import an RPM from an upload into a repository.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param upload_id: A string. The ID of an upload request.
    :param href: A string. The path to an RPM repository.
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.
    """
    return handle_response(requests.post(
        server_config.base_url + href + 'actions/import_upload/',
        json={'unit_key': {}, 'unit_type_id': 'rpm', 'upload_id': upload_id},
        **server_config.get_requests_kwargs()
    ), responses)


def _copy_repo(server_config, source_repo_id, href, responses=None):
    """Copy content from one repository to another.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param source_repo_id: A string. The ID of the source repository.
    :param href: A string. The path to the repository on which the association
        action is being performed. Content is copied to this repo.
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.
    """
    return handle_response(requests.post(
        server_config.base_url + href + 'actions/associate/',
        json={'source_repo_id': source_repo_id},
        **server_config.get_requests_kwargs()
    ), responses)


def _add_yum_distributor(server_config, href, responses=None):
    """Add a yum distributor to an RPM repository.

    The yum distributor will not automatically be published, and is available
    over HTTP and HTTPS. The distributor ID and relative URL are random.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to the repository to which a distributor
        shall be added.
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.
    """
    return handle_response(requests.post(
        server_config.base_url + href + 'distributors/',
        json={
            'auto_publish': False,
            'distributor_id': uuid4(),
            'distributor_type_id': 'yum_distributor',
            'distributor_config': {
                'http': True,
                'https': True,
                'relative_url': '/' + uuid4(),
            },
        },
        **server_config.get_requests_kwargs()
    ), responses)


def _gen_rpm_repo_body():
    """Return a semi-random dict that can be used for creating an RPM repo."""
    return {
        'id': uuid4(),
        'importer_config': {},
        'importer_type_id': 'yum_importer',
        'notes': {'_repo-type': 'rpm-repo'},
    }


class _BaseTestCase(TestCase):
    """Provide a server config, and tear down created resources."""

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an iterable of resources to delete."""
        cls.cfg = get_config()
        cls.attrs_iter = tuple()

    @classmethod
    def tearDownClass(cls):
        """Delete created resources."""
        for attrs in cls.attrs_iter:
            delete(cls.cfg, attrs['_href'])


class CreateTestCase(_BaseTestCase):
    """Create two RPM repositories, with and without feed URLs respectively."""

    @classmethod
    def setUpClass(cls):
        """Create two RPM repositories, with and without feeds."""
        super(CreateTestCase, cls).setUpClass()
        cls.bodies = tuple((_gen_rpm_repo_body() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {'feed': uuid4()}  # invalid feed
        cls.attrs_iter = tuple((
            create_repository(cls.cfg, body) for body in cls.bodies
        ))
        cls.importers_iter = tuple((
            get_importers(cls.cfg, attrs['_href']) for attrs in cls.attrs_iter
        ))

    def test_id_notes(self):
        """Valdiate the ``id`` and ``notes`` attributes for each repo."""
        for key in ('id', 'notes'):
            for body, attrs in zip(self.bodies, self.attrs_iter):
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
    """If a valid feed is given, the sync completes with no reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a valid feed and sync it."""
        super(SyncValidFeedTestCase, cls).setUpClass()
        body = _gen_rpm_repo_body()
        body['importer_config']['feed'] = _VALID_FEED
        cls.attrs_iter = (create_repository(cls.cfg, body),)
        cls.sync_repo = []  # raw responses
        report = sync_repository(
            cls.cfg,
            cls.attrs_iter[0]['_href'],
            cls.sync_repo,
        )
        cls.task_bodies = tuple(poll_spawned_tasks(cls.cfg, report))
        cls.repo_after_sync = get(cls.cfg, cls.attrs_iter[0]['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.sync_repo[0].status_code, 202)

    def test_task_error(self):
        """Assert each task's "error" field is null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertEqual(task_body['error'], None)

    def test_task_traceback(self):
        """Assert each task's "traceback" field is null."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertEqual(task_body['traceback'], None)

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertEqual(
                    len(task_body['progress_report']['yum_importer']['content']['error_details']),  # noqa pylint:disable=line-too-long
                    0
                )

    def test_unit_count_on_repo(self):
        """Verify that the sync added the correct number of units to the repo.

        Looks at the content counts on the repo.

        This also verifies that the counts themselves are getting set on the
        repo.

        I obtained these numbers by looking at the metadata in the remote
        repository.
        """
        counts = self.repo_after_sync.get('content_unit_counts', {})
        self.assertEqual(counts.get('rpm'), 32)
        self.assertEqual(counts.get('erratum'), 4)
        self.assertEqual(counts.get('package_group'), 2)
        self.assertEqual(counts.get('package_category'), 1)


class SyncInvalidFeedTestCase(_BaseTestCase):
    """If an invalid feed is given, the sync completes with reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with an invalid feed and sync it."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        body = _gen_rpm_repo_body()
        body['importer_config']['feed'] = uuid4()  # set an invalid feed
        cls.attrs_iter = (create_repository(cls.cfg, body),)  # see parent cls
        cls.sync_repo = []  # raw responses
        report = sync_repository(
            cls.cfg,
            cls.attrs_iter[0]['_href'],
            cls.sync_repo,
        )
        cls.task_bodies = tuple(poll_spawned_tasks(cls.cfg, report))

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.sync_repo[0].status_code, 202)

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
        """Assert each task's progress report contains error details."""
        self.skipTest('See: https://pulp.plan.io/issues/1376')
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertNotEqual(
                    task_body['progress_report']['yum_importer']['content']['error_details'],  # noqa pylint:disable=line-too-long
                    []
                )

    def test_number_tasks(self):
        """Assert that only one task was spawned."""
        self.assertEqual(len(self.task_bodies), 1)


class PublishTestCase(_BaseTestCase):
    """Upload an RPM to a repository, publish it and download the RPM."""

    @classmethod
    def setUpClass(cls):
        """Upload an RPM to a repo, copy it to another, publish and download.

        Create two RPM repositories, both without feeds. Upload an RPM to the
        first repository. Copy this content to the second repository. Add a
        distributor to the first repository, publish it, and download the RPM
        file uploaded earlier.
        """
        super(PublishTestCase, cls).setUpClass()
        # The server's raw `responses` don't matter to us here in `setUpClass`.
        # We don't need to know things like HTTP status codes or header values
        # here. We only need the JSON-decoded `bodies`. But we keep both so
        # that we can create rigorous test methods.
        cls.rpms = []  # binary blobs
        steps = {
            'upload_malloc',
            'upload',
            'import',
            'upload_free',
            'copy',
            'distribute',
            'publish',
            'search units',
        }
        cls.responses = {key: [] for key in steps}
        cls.bodies = {}

        # Download RPM.
        response = requests.get(_RPM_URL)
        response.raise_for_status()
        cls.rpms.append(response.content)

        # Create two repos. Start an upload request. Upload RPM to upload area.
        cls.attrs_iter = tuple((
            create_repository(cls.cfg, _gen_rpm_repo_body()) for _ in range(2)
        ))
        cls.bodies['upload_malloc'] = _start_content_upload(
            cls.cfg,
            cls.responses['upload_malloc']
        )
        cls.bodies['upload'] = _upload_file(
            cls.cfg,
            cls.bodies['upload_malloc']['_href'],
            cls.rpms[0],
            cls.responses['upload'],
        )

        # Import uploaded RPM into first repo. Poll. Delete upload request.
        cls.bodies['import'] = _import_rpm_to_repo(
            cls.cfg,
            cls.bodies['upload_malloc']['upload_id'],
            cls.attrs_iter[0]['_href'],
            cls.responses['import'],
        )
        tuple(poll_spawned_tasks(cls.cfg, cls.bodies['import']))
        cls.bodies['upload_free'] = delete(
            cls.cfg,
            cls.bodies['upload_malloc']['_href'],
            cls.responses['upload_free'],
        )

        # Copy content from first repo to second. Poll until done.
        cls.bodies['copy'] = _copy_repo(
            cls.cfg,
            cls.attrs_iter[0]['id'],
            cls.attrs_iter[1]['_href'],
            cls.responses['copy'],
        )
        tuple(poll_spawned_tasks(cls.cfg, cls.bodies['copy']))

        # Add a distributor to the first repository, then publish the repo to
        # the distributor. Poll the publish request.
        cls.bodies['distribute'] = _add_yum_distributor(
            cls.cfg,
            cls.attrs_iter[0]['_href'],
            cls.responses['distribute'],
        )
        cls.bodies['publish'] = publish_repository(
            cls.cfg,
            cls.attrs_iter[0]['_href'],
            cls.bodies['distribute']['id'],
            cls.responses['publish'],
        )
        tuple(poll_spawned_tasks(cls.cfg, cls.bodies['publish']))

        # Download the RPM. The [1:] strips a leading slash.
        url = ''.join((
            cls.cfg.base_url,
            _REPO_PUBLISH_PATH,
            cls.bodies['distribute']['config']['relative_url'][1:],
            '/',
            os.path.split(urlparse(_RPM_URL).path)[1],  # not [-1]?!
        ))
        response = requests.get(url, verify=cls.cfg.verify)
        response.raise_for_status()
        cls.rpms.append(response.content)

        # Search for all units in each of the two repositories.
        cls.bodies['search units'] = tuple((
            _get_units(cls.cfg, attrs['_href'], cls.responses['search units'])
            for attrs in cls.attrs_iter
        ))

    def test_sanity(self):
        """Verify we collected a correct set of response bodies.

        This test does not verify Pulp behaviour. Rather, it helps to ensure
        that this test is written correctly.
        """
        self.assertEqual(set(self.responses.keys()), set(self.bodies.keys()))

    def test_status_codes(self):
        """Verify the HTTP status code of each server response."""
        steps_codes = (
            ('upload_malloc', 201),
            ('upload', 200),
            ('import', 202),
            ('upload_free', 200),
            ('copy', 202),
            ('distribute', 201),
            ('publish', 202),
            ('search units', 200),
        )
        for step, code in steps_codes:
            with self.subTest((step, code)):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_call_reports_keys(self):
        """Verify each call report has the correct keys."""
        for step in {'import', 'copy', 'publish'}:
            with self.subTest(step=step):
                self.assertEqual(
                    frozenset(self.bodies[step].keys()),
                    CALL_REPORT_KEYS,
                )

    def test_call_reports_values(self):
        """Verify no call report contains any errors."""
        for step in {'import', 'copy', 'publish'}:
            for attr in ('result', 'error'):
                with self.subTest((step, attr)):
                    self.assertIsNone(self.bodies[step][attr])

    def test_upload_malloc(self):
        """Verify the response body for starting an upload request."""
        self.assertEqual(
            set(self.bodies['upload_malloc'].keys()),
            {'_href', 'upload_id'},
        )

    def test_upload(self):
        """Verify the response body for uploading an RPM."""
        self.assertEqual(self.bodies['upload'], None)

    def test_upload_free(self):
        """Verify the response body for ending an upload request."""
        self.assertEqual(self.bodies['upload_free'], None)

    def test_search_units(self):
        """Verify the two repositories have the same units."""
        self.assertEqual(
            set(unit['unit_id'] for unit in self.bodies['search units'][0]),
            set(unit['unit_id'] for unit in self.bodies['search units'][1]),
        )

    def test_rpms(self):
        """Verify the uploaded and downloaded RPMs are identical."""
        self.assertEqual(self.rpms[0], self.rpms[1])
