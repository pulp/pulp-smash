# coding=utf-8
"""Tests for syncing and publishing docker repositories."""
import hashlib
import json
import unittest

from packaging.version import Version

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_V1_FEED_URL,
    DOCKER_V2_FEED_URL,
)
from pulp_smash.tests.docker.cli import utils as docker_utils
from pulp_smash.tests.docker.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_BYTE_UNICODE = (type(b''), type(u''))


class _BaseTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Provide a server config and a repository ID."""
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        utils.pulp_admin_login(cls.cfg)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repository."""
        docker_utils.repo_delete(cls.cfg, cls.repo_id)


class _SuccessMixin(object):

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
        if (cls.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1909, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1909')
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V1_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        )
        cls.completed_proc = docker_utils.repo_sync(cls.cfg, cls.repo_id)


def _get_app_file(cfg, repo_id):
    """Return the text of the repo json app file."""
    cmd = 'sudo cat /var/lib/pulp/published/docker/v2/app/{}.json'
    cmd = cmd.format(repo_id).split()
    return json.loads(cli.Client(cfg).run(cmd).stdout)


def _get_tags(cfg, repo_id):
    """Return the tags for the repo."""
    path = '/pulp/docker/v2/{}/tags/list'.format(repo_id)
    return api.Client(cfg).get(path).json()


def _get_manifest(cfg, repo_id, tag):
    """Return the manifest of tag ``tag`` in repository ``repo_id``."""
    path = '/pulp/docker/v2/{}/manifests/{}'.format(repo_id, tag)
    return api.Client(cfg).get(path).json()


class SyncPublishV2TestCase(_SuccessMixin, _BaseTestCase):
    """Show it is possible to sync and publish a docker v2 repository.

    This test case targets `Pulp #1051`_, "As a user, I can publish v2
    repositories."

    .. _Pulp #1051: https://pulp.plan.io/issues/1051
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry.

        After doing the above, read the repository's JSON app file, tags, and
        the manifest of the first tag.

        This method requires Pulp 2.8 and above, and will raise a ``SkipTest``
        exception if run against an earlier version of Pulp.
        """
        super(SyncPublishV2TestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest.SkipTest('These tests require Pulp 2.8 or above.')
        if (cls.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1909, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1909')
        if (cls.cfg.version >= Version('2.10') and
                selectors.bug_is_untestable(2287, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2287')
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME,
        )
        cls.completed_proc = docker_utils.repo_sync(cls.cfg, cls.repo_id)
        cls.app_file = _get_app_file(cls.cfg, cls.repo_id)
        cls.tags = _get_tags(cls.cfg, cls.repo_id)
        cls.manifest = _get_manifest(cls.cfg, cls.repo_id, cls.tags['tags'][0])

    def test_app_file_registry_id(self):
        """Assert that the v2 app file has the correct ``repo-registry-id``."""
        self.assertEqual(self.app_file['repo-registry-id'], self.repo_id)

    def test_app_file_repository(self):
        """Assert that the v2 app file has the correct repository."""
        self.assertEqual(self.app_file['repository'], self.repo_id)

    def test_app_file_url(self):
        """Assert that the v2 app file has the correct url."""
        cmd = 'hostname --fqdn'
        fqdn = cli.Client(self.cfg).run(cmd.split()).stdout.strip()
        self.assertEqual(
            self.app_file['url'],
            'https://{}/pulp/docker/v2/{}/'.format(fqdn, self.repo_id)
        )

    def test_app_file_version(self):
        """Assert that the v2 app file has the correct version."""
        self.assertEqual(self.app_file['version'], 2)

    def test_app_file_protected(self):
        """Assert that the repository is not marked as protected."""
        self.assertFalse(self.app_file['protected'])

    def test_app_file_type(self):
        """Assert that the v2 app file has the correct type."""
        self.assertEqual(self.app_file['type'], 'pulp-docker-redirect')

    def test_blob_digests(self):
        """Assert that the checksum embedded in each blob's URL is correct.

        For each of the "fsLayers" in the repository manifest, download and
        checksum its blob, and compare this checksum to the one embedded in the
        blob's URL.
        """
        # Issue 1781 only affects RHEL 6.
        if (selectors.bug_is_untestable(1781, self.cfg.version) and
                cli.Client(self.cfg, cli.echo_handler).run((
                    'grep',
                    '-i',
                    'red hat enterprise linux server release 6',
                    '/etc/redhat-release',
                )).returncode == 0):
            self.skipTest('https://pulp.plan.io/issues/1781')

        for fs_layer in self.manifest['fsLayers']:
            with self.subTest(fs_layer=fs_layer):
                blob_sum = fs_layer['blobSum']
                blob = api.Client(self.cfg).get(
                    '/pulp/docker/v2/{}/blobs/{}'
                    .format(self.repo_id, blob_sum)
                ).content
                algo, expected_digest = blob_sum.split(':')
                hasher = getattr(hashlib, algo)()
                hasher.update(blob)
                self.assertEqual(expected_digest, hasher.hexdigest())

    def test_manifest_fslayers(self):
        """Verify the structure of each of the "fsLayers" in the manifest.

        Assert that "fsLayers" is a list of dicts, that each dict has a single
        "blobSum" key, and that this key corresponds to a string.
        """
        self.assertIsInstance(self.manifest['fsLayers'], list)
        for fs_layer in self.manifest['fsLayers']:
            with self.subTest(fs_layer=fs_layer):
                self.assertIsInstance(fs_layer, dict)
                self.assertEqual(set(fs_layer.keys()), {'blobSum'})
                self.assertIsInstance(fs_layer['blobSum'], _BYTE_UNICODE)

    def test_manifest_keys(self):
        """Assert that the manifest has the expected keys."""
        self.assertEqual(
            set(self.manifest.keys()),
            {
                u'architecture',
                u'fsLayers',
                u'history',
                u'name',
                u'schemaVersion',
                u'signatures',
                u'tag',
            }
        )

    def test_manifest_name(self):
        """Assert that the manifest of the first tag has the correct name."""
        self.assertEqual(self.manifest['name'], 'library/busybox')

    def test_manifest_schema_version(self):
        """Assert that the manifest has the expected schema version."""
        self.assertEqual(self.manifest['schemaVersion'], 1)

    def test_manifest_tag(self):
        """Assert that the manifest of the first tag has the correct tag."""
        self.assertEqual(self.manifest['tag'], self.tags['tags'][0])

    def test_tags_name(self):
        """Assert that the tags name is the repo_id."""
        self.assertEqual(self.tags['name'], self.repo_id)

    def test_tags_list(self):
        """Assert that the tags are a non-empty list of strings."""
        self.assertIsInstance(self.tags['tags'], list)
        self.assertGreater(len(self.tags['tags']), 0)
        for tag in self.tags['tags']:
            self.assertIsInstance(tag, _BYTE_UNICODE)


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
            raise unittest.SkipTest('These tests require Pulp 2.8 or above.')
        if (cls.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1909, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1909')
        # The split() drops 'library/'.
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=DOCKER_UPSTREAM_NAME.split('/')[-1],
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
            upstream_name=DOCKER_UPSTREAM_NAME,
        )
        cls.completed_proc = cli.Client(cls.cfg, cli.echo_handler).run(
            'pulp-admin docker repo sync run --repo-id {}'
            .format(cls.repo_id).split()
        )

    def test_return_code(self):
        """Assert the "sync" command has a non-zero return code."""
        if selectors.bug_is_untestable(427, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/427')
        self.assertNotEqual(self.completed_proc.returncode, 0)

    def test_task_succeeded(self):
        """Assert the phrase "Task Succeeded" is not in stdout."""
        self.assertNotIn('Task Succeeded', self.completed_proc.stdout)

    def test_task_failed(self):
        """Assert the phrase "Task Failed" is in stdout."""
        self.assertIn('Task Failed', self.completed_proc.stdout)
