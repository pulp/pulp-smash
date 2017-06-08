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
   http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from itertools import product
from urllib.parse import urljoin

from packaging.version import Version
from requests.exceptions import HTTPError

from pulp_smash import api, config, exceptions, selectors, utils
from pulp_smash.constants import (
    CALL_REPORT_KEYS,
    CONTENT_UPLOAD_PATH,
    PUPPET_FEED_2,
    PUPPET_MODULE_1,
    PUPPET_MODULE_2,
    PUPPET_MODULE_URL_1,
    PUPPET_MODULE_URL_2,
    PUPPET_QUERY_2,
    REPOSITORY_PATH,
)
from pulp_smash.tests.puppet.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.puppet.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CreateTestCase(utils.BaseAPITestCase):
    """Create two puppet repos, with and without feed URLs respectively."""

    @classmethod
    def setUpClass(cls):
        """Create two puppet repositories, with and without feed URLs."""
        super(CreateTestCase, cls).setUpClass()
        cls.bodies = tuple((gen_repo() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {
            'feed': 'http://' + utils.uuid4(),  # Pulp checks for a URI scheme
            'queries': [PUPPET_QUERY_2],
        }

        client = api.Client(cls.cfg, api.json_handler)
        cls.repos = []
        cls.importers_iter = []
        for body in cls.bodies:
            repo = client.post(REPOSITORY_PATH, body)
            cls.resources.add(repo['_href'])
            cls.repos.append(repo)
            cls.importers_iter.append(client.get(repo['_href'] + 'importers/'))

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repo."""
        for body, repo in zip(self.bodies, self.repos):  # for input, output:
            for key in {'id', 'notes'}:
                with self.subTest(body=body):
                    self.assertIn(key, repo)
                    self.assertEqual(body[key], repo[key])

    def test_number_importers(self):
        """Each repository should have only one importer."""
        for i, importers in enumerate(self.importers_iter):
            with self.subTest(i=i):
                self.assertEqual(len(importers), 1, importers)

    def test_importer_type_id(self):
        """Validate the ``importer_type_id`` attribute of each importer."""
        key = 'importer_type_id'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(body[key], importers[0][key])

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        key = 'config'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(body['importer_' + key], importers[0][key])


class SyncValidFeedTestCase(utils.BaseAPITestCase):
    """Create and sync puppet repositories with valid feeds."""

    def test_matching_query(self):
        """Sync a repository with a query that matches units.

        Assert that:

        * None of the sync tasks has an error message.
        * Searching for module :data:`pulp_smash.constants.PUPPET_MODULE_2`
          yields one result.
        * The synced-in module can be downloaded.
        """
        # Create and sync a repository.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'feed': PUPPET_FEED_2,
            'queries': [PUPPET_QUERY_2],
        }
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        self.sync_repo(repo)

        # Publish the repository.
        utils.publish_repo(self.cfg, repo)
        module = '/'.join((PUPPET_MODULE_2['author'], PUPPET_MODULE_2['name']))
        response = client.get(
            '/v3/releases',
            auth=('repository', repo['id']),
            params={'module': module},
        )
        self.assertEqual(len(response['results']), 1)

        # Download the Puppet module.
        module = utils.http_get(PUPPET_MODULE_URL_2)
        client.response_handler = api.safe_handler
        response = client.get(response['results'][0]['file_uri'])
        with self.subTest():
            self.assertEqual(module, response.content)
        with self.subTest():
            self.assertIn(
                response.headers['content-type'],
                ('application/gzip', 'application/x-gzip')
            )

    def test_non_matching_query(self):
        """Sync a repository with a query that doesn't match any units.

        Assert that:

        * None of the sync tasks has an error message.
        * Searching for module :data:`pulp_smash.constants.PUPPET_MODULE_2`
          yields no results.
        """
        # Create and sync a repository.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'feed': PUPPET_FEED_2,
            'queries': [PUPPET_QUERY_2.replace('-', '_')],
        }
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        self.sync_repo(repo)

        # Publish the repository.
        utils.publish_repo(self.cfg, repo)
        module = '/'.join((PUPPET_MODULE_2['author'], PUPPET_MODULE_2['name']))
        with self.assertRaises(HTTPError):
            client.get(
                '/v3/releases',
                auth=('repository', repo['id']),
                params={'module': module},
            )

    def sync_repo(self, repo):
        """Sync a repository, and verify no tasks contain an error message."""
        report = utils.sync_repo(self.cfg, repo).json()
        for task in api.poll_spawned_tasks(self.cfg, report):
            self.assertIsNone(
                task['progress_report']['puppet_importer']['metadata']['error_message']  # noqa pylint:disable=line-too-long
            )


class SyncInvalidFeedTestCase(utils.BaseAPITestCase):
    """If an invalid feed is given a sync should complete with errors."""

    @classmethod
    def setUpClass(cls):
        """Create a puppet repository with an invalid feed and sync it."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {'feed': 'http://' + utils.uuid4()}
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Trigger a repository sync and collect completed tasks.
        client.response_handler = api.echo_handler
        cls.report = client.post(urljoin(repo['_href'], 'actions/sync/'))
        cls.report.raise_for_status()
        cls.tasks = list(api.poll_spawned_tasks(cls.cfg, cls.report.json()))

    def test_status_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_number_tasks(self):
        """Assert only one task was spawned."""
        self.assertEqual(len(self.tasks), 1)

    def test_task_error_traceback(self):
        """Assert the task's "error" and "traceback" fields are non-null."""
        for key in {'error', 'traceback'}:
            with self.subTest(key=key):
                self.assertIsNotNone(self.tasks[0][key])

    def test_error_details(self):
        """Assert each task's progress report contains error details."""
        self.assertIsNotNone(
            self.tasks[0]['progress_report']['puppet_importer']['metadata']['error']  # noqa pylint:disable=line-too-long
        )


class SyncNoFeedTestCase(utils.BaseAPITestCase):
    """Create and sync a puppet repository with no feed.

    At least one of the sync tasks should fail. The task should fail in a
    graceful manner, without e.g. an internal tracebacks. This test targets
    `Pulp #2628 <https://pulp.plan.io/issues/2628>`_.
    """

    def test_all(self):
        """Create and sync a puppet repository with no feed."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(2628, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2628')

        # Create a repository.
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        # Sync the repository. An error *should* occur. We just want the error
        # to be sane.
        with self.assertRaises(exceptions.TaskReportError) as err:
            utils.sync_repo(cfg, repo)
        with self.subTest(comment='check task "error" field'):
            self.assertIsNotNone(err.exception.task['error'])
            self.assertNotEqual(
                err.exception.task['error']['description'],
                "'NoneType' object has no attribute 'endswith'"
            )
            self.assertNotEqual(err.exception.task['error']['code'], 'PLP0000')
        with self.subTest(comment='check task "exception" field'):
            self.assertIsNone(err.exception.task['exception'])
        with self.subTest(comment='check task "traceback" field'):
            self.assertIsNone(err.exception.task['traceback'])


class SyncValidManifestFeedTestCase(utils.BaseAPITestCase):
    """A valid Puppet manifest should sync correctly."""

    @classmethod
    def setUpClass(cls):
        """Create repository with the feed pointing to a valid manifest."""
        super(SyncValidManifestFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config'] = {
            'feed': 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/puppet_manifest/modules/'  # noqa pylint:disable=line-too-long
        }
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])

        # Trigger a repository sync and collect completed tasks.
        cls.report = utils.sync_repo(cls.cfg, repo)
        cls.tasks = list(api.poll_spawned_tasks(cls.cfg, cls.report.json()))

    def test_status_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_number_tasks(self):
        """Assert only one task was spawned."""
        self.assertEqual(len(self.tasks), 1)

    def test_task_progress_report(self):
        """Assert each task's progress report shows no errors."""
        for i, task in enumerate(self.tasks):
            with self.subTest(i=i):
                self.assertIsNone(
                    task['progress_report']['puppet_importer']['metadata']['error_message']  # noqa pylint:disable=line-too-long
                )


class PublishTestCase(utils.BaseAPITestCase):
    """Test repository syncing, publishing and data integrity.

    Test uploading custom puppet module to repository, copying content between
    repositories, querying puppet modules from pulp server and integrity of
    downloaded modules. Three query formats are tested as are provided by
    different puppet versions:

    * puppet version <= 3.3
    * 3.3 < puppet version < 3.6
    * puppet version > 3.6
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
        utils.reset_pulp(cls.cfg)  # See: https://pulp.plan.io/issues/1406
        cls.responses = {}
        cls.modules = []  # Raw puppet modules.

        # Download a puppet module and create two repositories.
        client = api.Client(cls.cfg, api.json_handler)
        repos = [client.post(REPOSITORY_PATH, gen_repo()) for _ in range(2)]
        for repo in repos:
            cls.resources.add(repo['_href'])
        client.response_handler = api.safe_handler
        cls.modules.append(utils.http_get(PUPPET_MODULE_URL_1))

        # Begin an upload request, upload a puppet module, move the puppet
        # module into a repository, and end the upload request.
        cls.responses['malloc'] = client.post(CONTENT_UPLOAD_PATH)
        cls.responses['upload'] = client.put(
            urljoin(cls.responses['malloc'].json()['_href'], '0/'),
            data=cls.modules[0],
        )
        cls.responses['import'] = client.post(
            urljoin(repos[0]['_href'], 'actions/import_upload/'),
            {
                'unit_key': {},
                'unit_type_id': 'puppet_module',
                'upload_id': cls.responses['malloc'].json()['upload_id'],
            },
        )
        cls.responses['free'] = client.delete(
            cls.responses['malloc'].json()['_href']
        )

        # Copy content from the first puppet repository to the second.
        cls.responses['copy'] = client.post(
            urljoin(repos[1]['_href'], 'actions/associate/'),
            {'source_repo_id': repos[0]['id']}
        )

        # Add a distributor to each repository. Publish each repository.
        for key in {'distribute', 'publish'}:
            cls.responses[key] = []
        for repo in repos:
            cls.responses['distribute'].append(client.post(
                urljoin(repo['_href'], 'distributors/'),
                {
                    'auto_publish': False,
                    'distributor_id': utils.uuid4(),
                    'distributor_type_id': 'puppet_distributor',
                    'distributor_config': {
                        'serve_http': True,
                        'serve_https': True,
                        'relative_url': '/' + utils.uuid4(),
                    },
                }
            ))
            cls.responses['publish'].append(client.post(
                urljoin(repo['_href'], 'actions/publish/'),
                {'id': cls.responses['distribute'][-1].json()['id']},
            ))

        # Query both distributors using all three query forms.
        cls.responses['puppet releases'] = []
        author_name = PUPPET_MODULE_1['author'] + '/' + PUPPET_MODULE_1['name']
        for repo in repos:
            if selectors.bug_is_untestable(1440, cls.cfg.version):
                continue
            cls.responses['puppet releases'].append(client.get(
                '/api/v1/releases.json',
                params={'module': author_name},
                auth=('.', repo['id']),
            ))
            cls.responses['puppet releases'].append(client.get(
                '/pulp_puppet/forge/repository/{}/api/v1/releases.json'
                .format(repo['id']),
                params={'module': author_name},
            ))
            if cls.cfg.version < Version('2.8'):
                continue
            cls.responses['puppet releases'].append(client.get(
                '/v3/releases',
                params={'module': author_name},
                auth=('repository', repo['id']),
            ))

        # Download each unit referenced by the queries above.
        for response in cls.responses['puppet releases']:
            body = response.json()
            if set(body.keys()) == {'pagination', 'results'}:  # Puppet >= 3.6
                path = body['results'][0]['file_uri']
            else:
                path = body[author_name][0]['file']
            cls.modules.append(client.get(path).content)

        # Search for all units in each of the two repositories.
        cls.responses['repo units'] = [
            utils.search_units(cls.cfg, repo, {}, api.safe_handler)
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
                ('puppet releases', 200),
                ('repo units', 200),
        ):
            with self.subTest(step=step):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_malloc(self):
        """Verify the response body for `creating an upload request`_.

        .. _creating an upload request:
           http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#creating-an-upload-request
        """
        keys = set(self.responses['malloc'].json().keys())
        self.assertLessEqual({'_href', 'upload_id'}, keys)

    def test_upload(self):
        """Verify the response body for `uploading bits`_.

        .. _uploading bits:
           http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#upload-bits
        """
        self.assertIsNone(self.responses['upload'].json())

    def test_call_report_keys(self):
        """Verify each call report has a sane structure.

        * `Import into a Repository
          <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#import-into-a-repository>`_
        * `Copying Units Between Repositories
          <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/associate.html#copying-units-between-repositories>`_
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
        <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#delete-an-upload-request>`_
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
        """Verify the two puppet repositories have the same content units."""
        bodies = [resp.json() for resp in self.responses['repo units']]
        self.assertEqual(
            set(unit['unit_id'] for unit in bodies[0]),  # This test is fragile
            set(unit['unit_id'] for unit in bodies[1]),  # due to hard-coded
        )  # indices. But the data is complex, and this makes things simpler.

    def test_unit_integrity(self):
        """Verify the integrity of the puppet modules downloaded from Pulp."""
        # First module is downloaded from the puppet forge, others from Pulp.
        for i, module in enumerate(self.modules[1:]):
            with self.subTest(i=i):
                self.assertEqual(self.modules[0], module)
