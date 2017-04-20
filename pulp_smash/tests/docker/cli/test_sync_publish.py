# coding=utf-8
"""Tests for syncing and publishing docker repositories."""
import unittest
from urllib.parse import urlsplit, urlunsplit

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_V1_FEED_URL,
    DOCKER_V2_FEED_URL,
)
from pulp_smash.tests.docker.cli import utils as docker_utils
from pulp_smash.tests.docker.utils import set_up_module


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

    def test_all(self):
        """Create, sync and publish a Docker v1 repository.

        Specifically, do the following:

        1. Create, sync and publish a Docker repository. Set the repository's
           feed to a v1 feed.
        2. Make Crane immediately re-read the metadata files published by Pulp.
           (Restart Apache.)
        3. Issue an HTTP GET request to ``/crane/repositories``, and verify the
           correct information is reported.
        """
        # Create, sync and publish a repository.
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', docker_utils.repo_create(
            self.cfg,
            enable_v1='true',
            enable_v2='false',
            feed=DOCKER_V1_FEED_URL,
            repo_id=repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        ).stdout)
        self.addCleanup(docker_utils.repo_delete, self.cfg, repo_id)
        self.verify_proc(docker_utils.repo_sync(self.cfg, repo_id))
        self.verify_proc(docker_utils.repo_publish(self.cfg, repo_id))

        # Make Crane read the metadata. (Now!)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))

        # Get and inspect /crane/repositories.
        client = self.make_crane_client(self.cfg)
        repos = client.get('/crane/repositories')
        self.assertIn(repo_id, repos.keys())
        with self.subTest():
            self.assertFalse(repos[repo_id]['protected'])
        with self.subTest():
            self.assertTrue(repos[repo_id]['image_ids'])
        with self.subTest():
            self.assertTrue(repos[repo_id]['tags'])


class SyncPublishV2TestCase(SyncPublishMixin, utils.BaseAPITestCase):
    """Create, sync, publish and interact with a Docker v2 repository."""

    @classmethod
    def setUpClass(cls):
        """Maybe skip this test case, and execute ``pulp-admin login``."""
        super().setUpClass()
        if selectors.bug_is_untestable(2287, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2287')

    def test_all(self):
        """Create, sync and publish a repository. Interact with it.

        Specifically, do the following:

        1. Create, sync and publish a Docker repository. Set the repository's
           feed to a v2 feed.
        2. Make Crane immediately re-read the metadata files published by Pulp.
           (Restart Apache.)
        3. Issue an HTTP GET request to ``/crane/repositories``, and verify the
           correct information is reported.
        """
        # Create, sync and publish a repository.
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', docker_utils.repo_create(
            self.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        ).stdout)
        self.addCleanup(docker_utils.repo_delete, self.cfg, repo_id)
        self.verify_proc(docker_utils.repo_sync(self.cfg, repo_id))
        self.verify_proc(docker_utils.repo_publish(self.cfg, repo_id))

        # Make Crane read the metadata. (Now!)
        cli.GlobalServiceManager(self.cfg).restart(('httpd',))

        # Get and inspect /crane/repositories.
        client = self.make_crane_client(self.cfg)
        repos = client.get('/crane/repositories')
        self.assertIn(repo_id, repos.keys())
        with self.subTest():
            self.assertFalse(repos[repo_id]['protected'])
        if selectors.bug_is_testable(2723, self.cfg.version):
            with self.subTest():
                self.assertTrue(repos[repo_id]['image_ids'])
            with self.subTest():
                self.assertTrue(repos[repo_id]['tags'])


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

        # Get and inspect /crane/repositories.
        client = self.make_crane_client(self.cfg)
        repos = client.get('/crane/repositories')
        self.assertIn(repo_id, repos.keys())
        with self.subTest():
            self.assertFalse(repos[repo_id]['protected'])
        if selectors.bug_is_testable(2723, self.cfg.version):
            with self.subTest():
                self.assertTrue(repos[repo_id]['image_ids'])
            with self.subTest():
                self.assertTrue(repos[repo_id]['tags'])


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
