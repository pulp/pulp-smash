# coding=utf-8
"""Tests for syncing and publishing docker repositories."""
from __future__ import unicode_literals
import hashlib
import json

import unittest2
from packaging.version import Version

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import DOCKER_V1_FEED_URL, DOCKER_V2_FEED_URL
from pulp_smash.tests.docker.cli import utils as docker_utils

_UPSTREAM_NAME = 'library/busybox'


class _BaseTestCase(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        """Provide a server config and a repository ID."""
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        docker_utils.login(cls.cfg)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repository."""
        docker_utils.repo_delete(cls.cfg, cls.repo_id)


class _SuccessMixin(object):

    def test_return_code(self):
        """Assert the "sync" command has a return code of 0."""
        self.assertEqual(self.completed_proc.returncode, 0)

    def test_task_succeeded(self):
        """Assert the phrase "Task Succeeded" is in stdout."""
        self.assertIn('Task Succeeded', self.completed_proc.stdout)

    def test_task_failed(self):
        """Assert the phrase "Task Failed" is not in stdout."""
        self.assertNotIn('Task Failed', self.completed_proc.stdout)


class SyncV1TestCase(_SuccessMixin, _BaseTestCase):
    """Show it is possible to sync a docker repository with a v1 registry."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v1 registry."""
        super(SyncV1TestCase, cls).setUpClass()
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V1_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=_UPSTREAM_NAME,
        )
        cls.completed_proc = docker_utils.repo_sync(cls.cfg, cls.repo_id)


class SyncPublishV2TestCase(_SuccessMixin, _BaseTestCase):
    """Show it is possible to sync and publish a docker v2 repository."""

    def __init__(self, *args, **kwargs):
        """Initialize the test class."""
        super(SyncPublishV2TestCase, self).__init__(*args, **kwargs)
        self._app_file = None
        self._tags = None
        self._manifest = None

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry.

        This method requires Pulp 2.8 and above, and will raise a ``SkipTest``
        exception if run against an earlier version of Pulp.
        """
        super(SyncPublishV2TestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=_UPSTREAM_NAME,
        )
        cls.completed_proc = docker_utils.repo_sync(cls.cfg, cls.repo_id)

        cls.client = api.Client(cls.cfg)

    def test_app_file_registry_id(self):
        """Assert that the v2 app file has the correct repo-registry-id."""
        app_file = self._get_app_file()
        self.assertEqual(app_file['repo-registry-id'], self.repo_id)

    def test_app_file_repository(self):
        """Assert that the v2 app file has the correct repository."""
        app_file = self._get_app_file()
        self.assertEqual(app_file['repository'], self.repo_id)

    def test_app_file_url(self):
        """Assert that the v2 app file has the correct url."""
        app_file = self._get_app_file()
        cmd = 'hostname --fqdn'
        fqdn = cli.Client(self.cfg).run(cmd.split()).stdout.strip()
        self.assertEqual(app_file['url'],
                         'https://{}/pulp/docker/v2/{}/'.format(
                             fqdn, self.repo_id))

    def test_app_file_version(self):
        """Assert that the v2 app file has the correct version."""
        app_file = self._get_app_file()
        self.assertEqual(app_file['version'], 2)

    def test_app_file_protected(self):
        """The repo should not be marked as protected."""
        app_file = self._get_app_file()
        self.assertEqual(app_file['protected'], False)

    def test_app_file_type(self):
        """Assert that the v2 app file has the correct type."""
        app_file = self._get_app_file()
        self.assertEqual(app_file['type'], 'pulp-docker-redirect')

    def test_blob_digests(self):
        """Assert that we can retrieve all of the Blobs correctly."""
        manifest = self._get_manifest()
        # A list of 2-tuples of (expected_digest, actual_digest)
        digests = []

        for blob_sum in manifest['fsLayers']:
            blob_sum = blob_sum['blobSum']
            blob = self.client.get(
                '/pulp/docker/v2/{}/blobs/{}'.format(
                    self.repo_id, blob_sum)).content
            algo, expected_digest = blob_sum.split(':')
            hasher = getattr(hashlib, algo)()
            hasher.update(blob)
            digests.append((expected_digest, hasher.hexdigest()))

        self.assertTrue(all([t[0] == t[1] for t in digests]))

    def test_manifest_fslayers(self):
        """
        Assert that the manifest fsLayers is a list of dictionaries.

        Each dictionary should have one key (blobSum) which should index a
        string.
        """
        manifest = self._get_manifest()
        self.assertTrue(isinstance(manifest['fsLayers'], list))
        self.assertTrue(
            all([isinstance(l, dict) for l in manifest['fsLayers']]))
        self.assertTrue(
            all([l.keys() == ['blobSum'] for l in manifest['fsLayers']]))
        self.assertTrue(
            all([isinstance(l['blobSum'], (type(''), type(u'')))
                 for l in manifest['fsLayers']]))

    def test_manifest_keys(self):
        """Assert that the manifest has the expected keys."""
        manifest = self._get_manifest()
        self.assertEqual(
            manifest.keys(),
            [u'signatures', u'name', u'tag', u'architecture', u'fsLayers',
             u'schemaVersion', u'history'])

    def test_manifest_name(self):
        """Assert that the manifest of the first tag has the correct name."""
        manifest = self._get_manifest()
        self.assertEqual(manifest['name'], 'library/busybox')

    def test_manifest_schema_version(self):
        """Assert that the manifest has the expected schema version."""
        manifest = self._get_manifest()
        self.assertEqual(manifest['schemaVersion'], 1)

    def test_manifest_tag(self):
        """Assert that the manifest of the first tag has the correct tag."""
        manifest = self._get_manifest()
        tags = self._get_tags()
        self.assertEqual(manifest['tag'], tags['tags'][0])

    def test_tags_name(self):
        """Assert that the tags name is the repo_id."""
        tags = self._get_tags()
        self.assertEqual(tags['name'], self.repo_id)

    def test_tags_list(self):
        """Assert that the list of tags is correct."""
        tags = self._get_tags()
        self.assertEqual(type(tags['tags']), list)
        # There has to be at least one tag in the list, though we don't have
        # any guarantees about what that tag should be.
        self.assertTrue(len(tags['tags']) > 0)
        # Every tag should be a string
        self.assertTrue(
            all([isinstance(t, (type(''), type(u''))) for t in tags['tags']]))

    def _get_app_file(self):
        """Return the text of the repo json app file."""
        if not self._app_file:
            cmd = 'sudo cat /var/lib/pulp/published/docker/v2/app/{}.json'
            cmd = cmd.format(self.repo_id)
            self._app_file = json.loads(
                cli.Client(self.cfg).run(cmd.split()).stdout)
        return self._app_file

    def _get_tags(self):
        """Return the tags for the repo."""
        if not self._tags:
            self._tags = self.client.get(
                '/pulp/docker/v2/{}/tags/list'.format(self.repo_id)).json()
        return self._tags

    def _get_manifest(self):
        """Return the manifest of the first tag."""
        if not self._manifest:
            first_tag = self._get_tags()['tags'][0]
            self._manifest = self.client.get(
                '/pulp/docker/v2/{}/manifests/{}'.format(
                    self.repo_id, first_tag))
            self._manifest = self._manifest.json()
        return self._manifest


class SyncUnnamespacedV2TestCase(_SuccessMixin, _BaseTestCase):
    """Show it Pulp can sync an unnamespaced docker repo from a v2 registry."""

    @classmethod
    def setUpClass(cls):
        """Create a docker repository from an unnamespaced v2 registry.

        This method requires Pulp 2.8 and above, and will raise a ``SkipTest``
        exception if run against an earlier version of Pulp.
        """
        super(SyncUnnamespacedV2TestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=_UPSTREAM_NAME.split('/')[-1],  # drop 'library/'
        )
        cls.completed_proc = docker_utils.repo_sync(cls.cfg, cls.repo_id)


class InvalidFeedTestCase(_BaseTestCase):
    """Show Pulp behaves correctly when syncing a repo with an invalid feed."""

    @classmethod
    def setUpClass(cls):
        """Create a docker repo with an invalid feed and sync it."""
        super(InvalidFeedTestCase, cls).setUpClass()
        docker_utils.repo_create(
            cls.cfg,
            feed='https://docker.example.com',
            repo_id=cls.repo_id,
            upstream_name=_UPSTREAM_NAME,
        )
        cls.completed_proc = cli.Client(cls.cfg, cli.echo_handler).run(
            'pulp-admin docker repo sync run --repo-id {}'
            .format(cls.repo_id).split()
        )

    def test_return_code(self):
        """Assert the "sync" command has a non-zero return code."""
        if selectors.bug_is_untestable(427):
            self.skipTest('https://pulp.plan.io/issues/427')
        self.assertNotEqual(self.completed_proc.returncode, 0)

    def test_task_succeeded(self):
        """Assert the phrase "Task Succeeded" is not in stdout."""
        self.assertNotIn('Task Succeeded', self.completed_proc.stdout)

    def test_task_failed(self):
        """Assert the phrase "Task Failed" is in stdout."""
        self.assertIn('Task Failed', self.completed_proc.stdout)
