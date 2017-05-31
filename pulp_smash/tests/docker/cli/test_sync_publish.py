# coding=utf-8
"""Tests for syncing and publishing docker repositories."""
import unittest
from urllib.parse import urlsplit, urlunsplit

from packaging.version import Version

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_V1_FEED_URL,
    DOCKER_V2_FEED_URL,
)
from pulp_smash.tests.docker.cli import utils as docker_utils
from pulp_smash.tests.docker.utils import set_up_module

from jsonschema import validate

IMAGE_MANIFEST_V2_SCHEMA_1 = {
    '$schema': 'http://json-schema.org/schema#',
    'title': 'Image Manifest Version 2, Schema 1',
    'description': (
        'Derived from: https://docs.docker.com/registry/spec/manifest-v2-1/'
    ),
    'type': 'object',
    'properties': {
        'architecture': {'type': 'string'},
        'fsLayers': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'blobSum': {'type': 'string'}},
            },
        },
        'history': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'v1Compatibility': {'type': 'string'}},
            },
        },
        'name': {'type': 'string'},
        'schemaVersion': {'type': 'integer'},
        'signatures': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'header': {
                        'type': 'object',
                        'properties': {
                            'jwk': {
                                'type': 'object',
                                'properties': {
                                    'crv': {'type': 'string'},
                                    'kid': {'type': 'string'},
                                    'kty': {'type': 'string'},
                                    'x': {'type': 'string'},
                                    'y': {'type': 'string'},
                                },
                            },
                            'alg': {'type': 'string'},
                        },
                    },
                    'protected': {'type': 'string'},
                    'signature': {'type': 'string'},
                },
            },
        },
        'tag': {'type': 'string'},
    },
}
"""A schema for docker v2 image manifests, schema 1."""

IMAGE_MANIFEST_V2_SCHEMA_2 = {
    '$schema': 'http://json-schema.org/schema#',
    'title': 'Image Manifest Version 2, Schema 2',
    'description': (
        'Derived from: https://docs.docker.com/registry/spec/manifest-v2-2/'
    ),
    'type': 'object',
    'properties': {
        'config': {
            'type': 'object',
            'properties': {
                'digest': {'type': 'string'},
                'mediaType': {'type': 'string'},
                'size': {'type': 'integer'},
            },
        },
        'layers': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'digest': {'type': 'string'},
                    'mediaType': {'type': 'string'},
                    'size': {'type': 'integer'},
                    'urls': {
                        'type': 'array',
                        'items': {'type': 'string'},
                    },
                },
            },
        },
        'mediaType': {'type': 'string'},
        'schemaVersion': {'type': 'integer'},
    },
}
"""A schema for docker v2 image manifests, schema 2."""


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login``."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


class SyncPublishMixin(object):
    """Tools for test cases that test repository syncing and publishing.

    This class must be mixed in to a class that inherits from
    ``unittest.TestCase``.
    """

    def verify_proc(self, proc):
        """Assert ``proc.stdout`` has correct contents.

        Assert "Task Succeeded" is present and "Task Failed" is absent.
        """
        self.assertIn('Task Succeeded', proc.stdout)
        self.assertNotIn('Task Failed', proc.stdout)

    @staticmethod
    def adjust_url(url):
        """Return a URL that can be used for talking with Crane.

        The URL returned is the same as ``url``, except that the scheme is set
        to HTTP, and the port is set to (or replaced by) 5000.

        :param url: A string, such as ``https://pulp.example.com/foo``.
        :returns: A string, such as ``http://pulp.example.com:5000/foo``.
        """
        parse_result = urlsplit(url)
        netloc = parse_result[1].partition(':')[0] + ':5000'
        return urlunsplit(('http', netloc) + parse_result[2:])

    @staticmethod
    def make_crane_client(cfg):
        """Make an API client for talking with Crane.

        Create an API client for talking to Crane. The client returned by this
        method is similar to the following ``client``:

        >>> client = api.Client(cfg, api.json_handler)

        However:

        * The client's base URL is adjusted as described by :meth:`adjust_url`.
        * The client will send an ``accept:application/json`` header with each
          request.

        :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
            deployment.
        :returns: An API client for talking with Crane.
        :rtype: pulp_smash.api.Client
        """
        client = api.Client(
            cfg,
            api.json_handler,
            {'headers': {'accept': 'application/json'}},
        )
        client.request_kwargs['url'] = SyncPublishMixin.adjust_url(
            client.request_kwargs['url']
        )
        return client


class SyncPublishV1TestCase(SyncPublishMixin, utils.BaseAPITestCase):
    """Create, sync, publish and interact with a Docker v1 repository."""

    @classmethod
    def setUpClass(cls):
        """Maybe skip this test case, and execute ``pulp-admin login``."""
        super().setUpClass()
        cls.repo_id = None

    @classmethod
    def tearDownClass(cls):
        """Destroy resources created by this test case."""
        if cls.repo_id:
            docker_utils.repo_delete(cls.cfg, cls.repo_id)
        super().tearDownClass()

    def test_01_set_up(self):
        """Create, sync and publish a repository.

        Specifically, do the following:

        1. Create, sync and publish a Docker repository. Set the repository's
           feed to a v1 feed.
        2. Make Crane immediately re-read the metadata files published by Pulp.
           (Restart Apache.)
        """
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', docker_utils.repo_create(
            self.cfg,
            enable_v1='true',
            enable_v2='false',
            feed=DOCKER_V1_FEED_URL,
            repo_id=repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        ).stdout)
        type(self).repo_id = repo_id
        self.verify_proc(docker_utils.repo_sync(self.cfg, repo_id))
        self.verify_proc(docker_utils.repo_publish(self.cfg, repo_id))

        # Make Crane read the metadata. (Now!)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))

    @selectors.skip_if(bool, 'repo_id', False)
    def test_02_get_crane_repositories(self):
        """Issue an HTTP GET request to ``/crane/repositories``.

        Assert that the response is as described by `Crane Admin
        <http://docs.pulpproject.org/plugins/crane/index.html#crane-admin>`_.
        """
        repos = self.make_crane_client(self.cfg).get('/crane/repositories')
        self.assertIn(self.repo_id, repos.keys())
        self.verify_v1_repo(repos[self.repo_id])

    @selectors.skip_if(bool, 'repo_id', False)
    def test_02_get_crane_repositories_v1(self):  # pylint:disable=invalid-name
        """Issue an HTTP GET request to ``/crane/repositories/v1``.

        Assert that the response is as described by `Crane Admin
        <http://docs.pulpproject.org/plugins/crane/index.html#crane-admin>`_.
        """
        if (self.cfg.version < Version('2.14') or
                selectors.bug_is_untestable(2723, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2723')
        repos = self.make_crane_client(self.cfg).get('/crane/repositories/v1')
        self.assertIn(self.repo_id, repos.keys())
        self.verify_v1_repo(repos[self.repo_id])

    def verify_v1_repo(self, repo):
        """Implement the assertions for the ``test_02*`` methods."""
        with self.subTest():
            self.assertFalse(repo['protected'])
        with self.subTest():
            self.assertTrue(repo['image_ids'])
        with self.subTest():
            self.assertTrue(repo['tags'])


class SyncPublishV2TestCase(SyncPublishMixin, utils.BaseAPITestCase):
    """Create, sync, publish and interact with a Docker v2 repository."""

    @classmethod
    def setUpClass(cls):
        """Maybe skip this test case, and execute ``pulp-admin login``."""
        super().setUpClass()
        if selectors.bug_is_untestable(2287, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2287')
        cls.repo_id = None

    @classmethod
    def tearDownClass(cls):
        """Destroy resources created by this test case."""
        if cls.repo_id:
            docker_utils.repo_delete(cls.cfg, cls.repo_id)
        super().tearDownClass()

    def test_01_set_up(self):
        """Create, sync and publish a repository.

        Specifically, do the following:

        1. Create, sync and publish a Docker repository. Set the repository's
           feed to a v2 feed.
        2. Make Crane immediately re-read the metadata files published by Pulp.
           (Restart Apache.)
        """
        repo_id = utils.uuid4()
        proc = docker_utils.repo_create(
            self.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        )
        type(self).repo_id = repo_id  # schedule clean-up
        self.assertNotIn('Task Failed', proc.stdout)
        self.verify_proc(docker_utils.repo_sync(self.cfg, repo_id))
        self.verify_proc(docker_utils.repo_publish(self.cfg, repo_id))

        # Make Crane read the metadata. (Now!)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))

    @selectors.skip_if(bool, 'repo_id', False)
    def test_02_get_crane_repositories_v2(self):  # pylint:disable=invalid-name
        """Issue an HTTP GET request to ``/crane/repositories/v2``.

        Assert that the response is as described by `Crane Admin
        <http://docs.pulpproject.org/plugins/crane/index.html#crane-admin>`_.
        """
        if (self.cfg.version < Version('2.14') or
                selectors.bug_is_untestable(2723, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2723')
        repos = self.make_crane_client(self.cfg).get('/crane/repositories/v2')
        self.assertIn(self.repo_id, repos.keys())
        repo = repos[self.repo_id]
        self.assertFalse(repo['protected'])

    @selectors.skip_if(bool, 'repo_id', False)
    def test_02_get_manifest_v1(self):
        """Issue an HTTP GET request to ``/v2/{repo_id}/manifests/latest``.

        Pass a header of
        ``accept:application/vnd.docker.distribution.manifest.v1+json``. Assert
        that the response is as described by `Image Manifest Version 2, Schema
        1 <https://docs.docker.com/registry/spec/manifest-v2-1/>`_.

        This test targets `Pulp #2336 <https://pulp.plan.io/issues/2336>`_.
        """
        if selectors.bug_is_untestable(2336, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2336')
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.adjust_url(
            client.request_kwargs['url']
        )
        headers_iter = (
            {},
            {'accept': 'application/json'},
            {'accept': 'application/vnd.docker.distribution.manifest.v1+json'},
        )
        for headers in headers_iter:
            with self.subTest(headers=headers):
                manifest = client.get(
                    '/v2/{}/manifests/latest'.format(self.repo_id),
                    headers=headers,
                )
                validate(manifest, IMAGE_MANIFEST_V2_SCHEMA_1)

    @selectors.skip_if(bool, 'repo_id', False)
    def test_02_get_manifest_v2(self):
        """Issue an HTTP GET request to ``/v2/{repo_id}/manifests/latest``.

        Pass a header of
        ``accept:application/vnd.docker.distribution.manifest.v2+json``. Assert
        that the response is as described by `Image Manifest Version 2, Schema
        2 <https://docs.docker.com/registry/spec/manifest-v2-2/>`_.

        This test targets `Pulp #2336 <https://pulp.plan.io/issues/2336>`_.
        """
        if selectors.bug_is_untestable(2336, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2336')
        client = api.Client(self.cfg, api.json_handler, {'headers': {
            'accept': 'application/vnd.docker.distribution.manifest.v2+json'
        }})
        client.request_kwargs['url'] = self.adjust_url(
            client.request_kwargs['url']
        )
        manifest = client.get('/v2/{}/manifests/latest'.format(self.repo_id))
        validate(manifest, IMAGE_MANIFEST_V2_SCHEMA_2)


class SyncNonNamespacedV2TestCase(SyncPublishMixin, utils.BaseAPITestCase):
    """Create, sync and publish a non-namespaced repository."""

    def test_all(self):
        """Create, sync and publish a non-namespaced repository."""
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', docker_utils.repo_create(
            self.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME.split('/')[-1],  # drop library/
        ).stdout)
        self.addCleanup(docker_utils.repo_delete, self.cfg, repo_id)
        self.verify_proc(docker_utils.repo_sync(self.cfg, repo_id))
        self.verify_proc(docker_utils.repo_publish(self.cfg, repo_id))

        # Make Crane read the metadata. (Now!)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))

        # Get and inspect /crane/repositories/v2.
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_testable(2723, self.cfg.version)):
            client = self.make_crane_client(self.cfg)
            repos = client.get('/crane/repositories/v2')
            self.assertIn(repo_id, repos.keys())
            with self.subTest():
                self.assertFalse(repos[repo_id]['protected'])


class InvalidFeedTestCase(utils.BaseAPITestCase):
    """Show Pulp behaves correctly when syncing a repo with an invalid feed."""

    def test_all(self):
        """Create a docker repo with an invalid feed and sync it."""
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', docker_utils.repo_create(
            self.cfg,
            feed='https://docker.example.com',
            repo_id=repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        ).stdout)
        self.addCleanup(docker_utils.repo_delete, self.cfg, repo_id)
        client = cli.Client(self.cfg, cli.echo_handler)
        proc = client.run((
            'pulp-admin', 'docker', 'repo', 'sync', 'run', '--repo-id', repo_id
        ))
        if selectors.bug_is_testable(427, self.cfg.version):
            with self.subTest():
                self.assertNotEqual(proc.returncode, 0)
        with self.subTest():
            self.assertNotIn('Task Succeeded', proc.stdout)
        with self.subTest():
            self.assertIn('Task Failed', proc.stdout)


class RepoRegistryIdTestCase(SyncPublishMixin, utils.BaseAPITestCase):
    """Show Pulp can publish repos with varying ``repo_registry_id`` values.

    The ``repo_registry_id`` setting defines a repository's name as seen by
    clients such as the Docker CLI. It's traditionally a two-part name such as
    ``docker/busybox``, but according to `Pulp #2368`_, it can contain an
    arbitrary number of slashes. This test case verifies that the
    ``repo_registry_id`` can be set to values containing varying numbers of
    slashes.

    Also see: `Pulp #2723 <https://pulp.plan.io/issues/2723>`_.

    .. _Pulp #2368: https://pulp.plan.io/issues/2368
    """

    def test_zero_slashes(self):
        """Give ``repo_registry_id`` zero slashes."""
        if (self.cfg.version < Version('2.14') or
                selectors.bug_is_untestable(2723, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2723')
        repo_registry_id = '/'.join(utils.uuid4() for _ in range(1))
        self.create_sync_publish_repo(repo_registry_id)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))  # restart Crane

        # Get and inspect /crane/repositories/v2.
        client = self.make_crane_client(self.cfg)
        repos = client.get('/crane/repositories/v2')
        self.assertIn(repo_registry_id, repos.keys())
        with self.subTest():
            self.assertFalse(repos[repo_registry_id]['protected'])

    def test_one_slash(self):
        """Give ``repo_registry_id`` one slash."""
        if (self.cfg.version < Version('2.14') or
                selectors.bug_is_untestable(2723, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2723')
        repo_registry_id = '/'.join(utils.uuid4() for _ in range(2))
        self.create_sync_publish_repo(repo_registry_id)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))  # restart Crane

        # Get and inspect /crane/repositories/v2.
        client = self.make_crane_client(self.cfg)
        repos = client.get('/crane/repositories/v2')
        self.assertIn(repo_registry_id, repos.keys())
        with self.subTest():
            self.assertFalse(repos[repo_registry_id]['protected'])

    def test_two_slashes(self):
        """Give ``repo_registry_id`` two slashes."""
        if (self.cfg.version < Version('2.14') or
                selectors.bug_is_untestable(2723, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2723')
        repo_registry_id = '/'.join(utils.uuid4() for _ in range(3))
        self.create_sync_publish_repo(repo_registry_id)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))  # restart Crane

        # Get and inspect /crane/repositories/v2.
        client = self.make_crane_client(self.cfg)
        repos = client.get('/crane/repositories/v2')
        self.assertIn(repo_registry_id, repos.keys())
        with self.subTest():
            self.assertFalse(repos[repo_registry_id]['protected'])

    def create_sync_publish_repo(self, repo_registry_id):
        """Create, sync and publish a Docker repository.

        Also, schedule the repository for deletion with ``addCleanup``.

        :param repo_registry_id: Passed to
            :meth:`pulp_smash.tests.docker.cli.utils.repo_create`.
        :returns: Nothing.
        """
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', docker_utils.repo_create(
            self.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=repo_id,
            repo_registry_id=repo_registry_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        ).stdout)
        self.addCleanup(docker_utils.repo_delete, self.cfg, repo_id)
        self.verify_proc(docker_utils.repo_sync(self.cfg, repo_id))
        self.verify_proc(docker_utils.repo_publish(self.cfg, repo_id))
