# coding=utf-8
"""Test the API endpoints for puppet `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an puppet repo with a feed. (CreateTestCase)
    ├── If a valid feed is given, the sync completes and no errors are
    │   reported for both valid and ivalid query. (SyncValidFeedTestCase)
    └── If an invalid feed is given, the sync completes and errors are
        reported. (SyncInvalidFeedTestCase)

    It is possible to create an puppet repo without a feed. (CreateTestCase)
    └── It is possible to upload an puppet module to a repository, copy the
        repository's content to a second repository, add distributor to
        both repositories, publish them and query modules back. Data integrity
        of modules queried from pulp server is preserved. (PublishTestCase)

Assertions not explored in this module include:

* Given an puppet repository without a feed, sync requests fail.
* It is not possible to create two puppet repos with the same relative URL.
* It is possible to upload a directory of puppet modules to an repository.
* It is possible to upload content and copy it into multiple repositories.
* It is possible to get content into a repository via a sync and publish it.
* Functionality of puppet_install_distributor which install puppet module on
  pulp server.
* Functionality of puppet_file_distributor which makes puppet modules available
  in single directory on pulp server over HTTPS.

.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html

"""
from __future__ import unicode_literals

from itertools import chain
from packaging.version import Version
from pulp_smash.config import get_config
from pulp_smash.constants import CALL_REPORT_KEYS
from pulp_smash.utils import (
    create_repository,
    delete,
    get_importers,
    handle_response,
    poll_spawned_tasks,
    publish_repository,
    sync_repository,
    uuid4,
)
from unittest2 import TestCase
import hashlib
import requests

_VALID_PUPPET_FEED = 'http://forge.puppetlabs.com'
_VALID_PUPPET_QUERY = 'pulp-pulp'
_INVALID_PUPPET_QUERY = 'invalid_puppet_query'
_PUPPET_QUERY_URL = (
    'http://forge.puppetlabs.com'
    '/v3/files/pulp-pulp-1.0.0.tar.gz'
)
_PUPPET_QUERY_PACKAGE = {
    'name': 'pulp',
    'author': 'pulp'
}
_PUPPET_DIRECT_URL = (
    'https://repos.fedorapeople.org/'
    'pulp/pulp/demo_repos/puppet_symlink/examplecorp-mymodule-0.1.0.tar.gz'
)

_TASK_END_STATES = ('canceled', 'error', 'finished', 'skipped', 'timed out')
_REPO_PUBLISH_PATH = '/pulp/puppet/'  # + relative_url + puppet-module
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


def _query_repo_old(server_config, query_url, repo_id, responses=None):
    """Query pulp puppet repo for presence of given unit (puppet ver. <3.3).

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param query_url: Url in Puppet Forge formatted URL. URL is formatted as
                        '/api/v1/releases.json?module=modulename/author'
    :param repo_id: id of queried repository
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.

    """
    kwargs = server_config.get_requests_kwargs()
    kwargs['auth'] = ('.', repo_id)
    return handle_response(requests.get(
        server_config.base_url + query_url,
        **kwargs
    ), responses)


def _query_repo_middle(server_config, query_url, responses=None):
    """Query pulp puppet repo for presence of given unit (puppet ver. 3.4-3.5).

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param query_url: Url in Puppet Forge formatted URL. URL is formatted as
    '/pulp_puppet/forge/repository/repo_id/api/v1/releases.json?module=modulename/author'
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.

    """
    return handle_response(requests.get(
        server_config.base_url + query_url,
        **server_config.get_requests_kwargs()
    ), responses)


def _query_repo_new(server_config, query_url, repo_id, responses=None):
    """Query pulp puppet repo for presence of given unit (puppet ver. >=3.6).

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param query_url: Url in Puppet Forge formatted URL. URL is formatted as
        /v3/releases?module=modulename/author
    :param repo_id: id of queried repository
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.

    """
    kwargs = server_config.get_requests_kwargs()
    kwargs['auth'] = ('repository', repo_id)
    return handle_response(requests.get(
        server_config.base_url + query_url,
        **kwargs
    ), responses)


def _import_puppet_module_into_repo(
        server_config, upload_id, href, responses=None):
    """Import an puppet from an upload into a repository.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param upload_id: A string. The ID of an upload request.
    :param href: A string. The path to an puppet repository.
    :param responses: A list, or some other object that supports the ``append``
        method. If given, all server responses are appended to this object.
    :returns: The server's JSON-decoded response.

    """
    return handle_response(requests.post(
        server_config.base_url + href + 'actions/import_upload/',
        json={
            'unit_key': {},
            'unit_type_id': 'puppet_module',
            'upload_id': upload_id
        },
        **server_config.get_requests_kwargs()
    ), responses)


def _add_puppet_distributor(server_config, href, responses=None):
    """Add a puppet distributor to a puppet repository.

    The puppet distributor will not be published automatically and is available
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
            'distributor_type_id': 'puppet_distributor',
            'distributor_config': {
                'serve_http': True,
                'serve_https': True,
                'relative_url': '/' + uuid4(),
            },
        },
        **server_config.get_requests_kwargs()
    ), responses)


def _gen_puppet_repo_body():
    """Return a semi-random dict that used for creating a puppet repo."""
    return {
        'id': uuid4(),
        'importer_config': {},
        'importer_type_id': 'puppet_importer',
        'notes': {'_repo-type': 'puppet-repo'},
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
    """Create two puppet repos, with and without feed URLs respectively."""

    @classmethod
    def setUpClass(cls):
        """Create two puppet repositories, with and without feeds."""
        super(CreateTestCase, cls).setUpClass()
        cls.bodies = tuple((_gen_puppet_repo_body() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {
            'feed': 'http://' + uuid4(),
            'queries': [_VALID_PUPPET_QUERY],
        }
        cls.attrs_iter = tuple((
            create_repository(cls.cfg, body) for body in cls.bodies
        ))
        cls.importers_iter = tuple((
            get_importers(cls.cfg, attrs['_href']) for attrs in cls.attrs_iter
        ))

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repo."""
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
    """Test creating repository with valid feed.

    Create two repositories wih valid feeds, one with valid and one with
    invalid query. Check that sync finish succesfully in both of them.

    """

    @classmethod
    def setUpClass(cls):
        """Create an puppet repositories with a valid feed and sync it."""
        super(SyncValidFeedTestCase, cls).setUpClass()
        bodies = tuple((_gen_puppet_repo_body() for i in range(2)))
        bodies[0]['importer_config'] = {
            'feed': _VALID_PUPPET_FEED,
            'queries': [_VALID_PUPPET_QUERY],
        }
        bodies[1]['importer_config'] = {
            'feed': _VALID_PUPPET_FEED,
            'queries': [_INVALID_PUPPET_QUERY],
        }
        cls.attrs_iter = tuple((
            create_repository(cls.cfg, body) for body in bodies
        ))
        cls.sync_repo = []  # raw responses
        cls.task_bodies = tuple((chain.from_iterable(  # response bodies
            poll_spawned_tasks(cls.cfg, call_report)
            for call_report in (sync_repository(
                cls.cfg,
                attr_iter['_href'],
                cls.sync_repo
            ) for attr_iter in cls.attrs_iter)
        )))

    def test_start_sync_code(self):
        """Assert the call to sync each repository returns an HTTP 202."""
        for i, sync_response in enumerate(self.sync_repo):
            with self.subTest(i=i):
                self.assertEqual(sync_response.status_code, 202)

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
                    task_body['progress_report']['puppet_importer']['metadata']['error_message'],  # noqa pylint:disable=line-too-long
                    None
                )


class SyncInvalidFeedTestCase(_BaseTestCase):
    """If an invalid feed is given, the sync completes with reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create puppet repository with an invalid feed and sync it."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        body = _gen_puppet_repo_body()
        body['importer_config'] = {'feed': 'http://' + uuid4()}
        cls.attrs_iter = (create_repository(cls.cfg, body),)
        cls.sync_repo = []  # raw responses
        cls.task_bodies = tuple((chain.from_iterable(  # response bodies
            poll_spawned_tasks(cls.cfg, call_report)
            for call_report in (sync_repository(
                cls.cfg,
                attr_iter['_href'],
                cls.sync_repo
            ) for attr_iter in cls.attrs_iter)
        )))

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
        for i, task_body in enumerate(self.task_bodies):
            with self.subTest(i=i):
                self.assertNotEqual(
                    task_body['progress_report']['puppet_importer']['metadata']['error'],  # noqa pylint:disable=line-too-long
                    None
                )

    def test_number_tasks(self):
        """Assert that only one task was spawned."""
        self.assertEqual(len(self.task_bodies), 1)


class PublishTestCase(_BaseTestCase):
    """Test repository syncing, publishing and data integrity.

    Test uploading custom puppet module to repository, copying content between
    repositories, querying puppet modules from pulp server and integrity of
    downloaded modules. Three query formats are tested as are provided
    by different puppet versions: puppet ver. <= 3.3, 3.3 < puppet ver. < 3.6
    and puppet ver. > 3.6.

    """

    @classmethod
    def setUpClass(cls):
        """Upload puppet module to a repo, copy it to another, publish and download.

        Create two puppet repositories, both without feeds. Upload an module to
        the first repository. Copy its content to the second repository. Add
        distributors to the repositories, publish repositories and download
        modules back from them.

        """
        super(PublishTestCase, cls).setUpClass()
        # The server's raw `responses` don't matter to us here in `setUpClass`.
        # We don't need to know things like HTTP status codes or header values
        # here. We only need the JSON-decoded `bodies`. But we keep both so
        # that we can create rigorous test methods.
        steps = {
            'upload_malloc',
            'upload',
            'import',
            'upload_free',
            'copy',
            'publish',
            'distribute',
            'search units',
            'query units',
        }
        cls.responses = {key: [] for key in steps}
        cls.bodies = {}
        cls.original_puppets = []  # binary blobs

        # Download puppet modules.
        response = requests.get(_PUPPET_QUERY_URL)
        response.raise_for_status()
        cls.original_puppets.append(response.content)

        # Create two repos, start upload request, upload module to upload dir
        cls.attrs_iter = tuple((
            create_repository(cls.cfg, _gen_puppet_repo_body())
            for _ in range(2)
        ))
        cls.bodies['upload_malloc'] = _start_content_upload(
            cls.cfg,
            cls.responses['upload_malloc']
        )
        cls.bodies['upload'] = _upload_file(
            cls.cfg,
            cls.bodies['upload_malloc']['_href'],
            cls.original_puppets[0],
            cls.responses['upload'],
        )

        # Import uploaded puppet modules into first repo. Poll.
        # Delete upload request.
        cls.bodies['import'] = _import_puppet_module_into_repo(
            cls.cfg,
            cls.bodies['upload_malloc']['upload_id'],
            cls.attrs_iter[0]['_href'],
            cls.responses['import'],
        )
        for call_report in cls.bodies['import']:
            poll_spawned_tasks(cls.cfg, call_report)
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
        for call_report in cls.bodies['copy']:
            poll_spawned_tasks(cls.cfg, call_report)

        # Add a distributor to the repositories, then publish repositories
        # to the distributors. Poll the publish request.
        cls.bodies['distribute'] = tuple((
            _add_puppet_distributor(
                cls.cfg,
                attr['_href'],
                cls.responses['distribute']
            ) for attr in cls.attrs_iter
        ))
        cls.bodies['publish'] = tuple((
            publish_repository(
                cls.cfg,
                cls.attrs_iter[i]['_href'],
                cls.bodies['distribute'][i]['id'],
                cls.responses['publish'],
            ) for i in range(2)  # Both tuples are always of size 2
        ))
        for publish_report in cls.bodies['publish']:
            for call_report in publish_report:
                poll_spawned_tasks(cls.cfg, call_report)

        # Form query as appears in puppet versions <=3.3
        query_href_old = '/api/v1/releases.json?module={}/{}'.format(
            _PUPPET_QUERY_PACKAGE['name'],
            _PUPPET_QUERY_PACKAGE['author']
        )
        # Form query as appears in puppet 3.3 < version < 3.6
        # This is list joined by repository name, ie. 'repoid'.join()
        query_href_middle = [
            '/pulp_puppet/forge/repository/',
            '/api/v1/releases.json?module={}/{}'.format(
                _PUPPET_QUERY_PACKAGE['name'],
                _PUPPET_QUERY_PACKAGE['author']
            )
        ]
        # Form query as appears in new puppet version (>=3.6).
        query_href_new = '/v3/releases?module={}/{}'.format(
            _PUPPET_QUERY_PACKAGE['name'],
            _PUPPET_QUERY_PACKAGE['author']
        )

        # Query server using url as in puppet <= 3.3
        cls.bodies['query units'] = tuple()
        cls.bodies['query units'] += tuple(
            _query_repo_old(
                cls.cfg,
                query_href_old,
                body['repo_id'],
                cls.responses['query units']
            ) for body in cls.bodies['distribute']
        )

        # Query server using url as in puppet 3.3 > pup. version < 3.6
        cls.bodies['query units'] += tuple(
            _query_repo_middle(
                cls.cfg,
                body['repo_id'].join(query_href_middle),
                cls.responses['query units']
            ) for body in cls.bodies['distribute']
        )

        # Query server using new url format (puppet >= 3.6)
        if cls.cfg.version > Version('2.6'):
            cls.bodies['query units'] += tuple(
                _query_repo_new(
                    cls.cfg,
                    query_href_new,
                    body['repo_id'],
                    cls.responses['query units']
                ) for body in cls.bodies['distribute']
            )

        module_uris = []  # Save modules' uri on server
        for query_body in cls.bodies['query units']:
            try:
                module_uris.append(
                    query_body['{}/{}'.format(
                        _PUPPET_QUERY_PACKAGE['name'],
                        _PUPPET_QUERY_PACKAGE['author'])][0]['file']
                )
            except KeyError:
                module_uris.append(query_body['results'][0]['file_uri'])

        # Download units from locations returned by query above
        cls.downloaded_puppets = tuple((
            requests.get(
                cls.cfg.base_url +
                module_uri,
                **cls.cfg.get_requests_kwargs()
            ) for module_uri in set(module_uris)
        ))

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
            ('query units', 200),
        )
        for step, code in steps_codes:
            with self.subTest((step, code)):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_call_reports_keys(self):
        """Verify each call report has the correct keys."""
        for step in {'import', 'copy'}:
            with self.subTest(step=step):
                self.assertEqual(
                    set(self.bodies[step].keys()),
                    CALL_REPORT_KEYS
                )
        # same for publish
        for body in self.bodies['publish']:
            with self.subTest(call_report=body):
                self.assertEqual(
                    set(body.keys()),
                    CALL_REPORT_KEYS
                )

    def test_call_reports_values(self):
        """Verify no call report contains any errors."""
        for step in {'import', 'copy'}:
            for attr in ('result', 'error'):
                with self.subTest((step, attr)):
                    self.assertIsNone(self.bodies[step][attr])
        # same for publish
        for body in self.bodies['publish']:
            for attr in ('result', 'error'):
                with self.subTest((body, attr)):
                    self.assertIsNone(body[attr])

    def test_upload_malloc(self):
        """Verify the response body for starting an upload request."""
        self.assertEqual(
            set(self.bodies['upload_malloc'].keys()),
            {'_href', 'upload_id'},
        )

    def test_upload(self):
        """Verify the response body for uploading module."""
        self.assertEqual(self.bodies['upload'], None)

    def test_upload_free(self):
        """Verify  the response body for ending an upload request."""
        self.assertEqual(self.bodies['upload_free'], None)

    def test_search_units(self):
        """Verify the two repositories have the same units."""
        self.assertEqual(
            set(unit['unit_id'] for unit in self.bodies['search units'][0]),
            set(unit['unit_id'] for unit in self.bodies['search units'][1]),
        )

    def test_units_integrity(self):
        """Verify integrity of modules downloaded from pulp server."""
        for puppy in self.downloaded_puppets:
            with self.subTest(response=puppy):
                self.assertEqual(
                    hashlib.sha256(self.original_puppets[0]).hexdigest(),
                    hashlib.sha256(puppy.content).hexdigest()
                )
