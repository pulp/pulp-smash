# coding=utf-8
"""Tests for syncing docker repositories."""
from __future__ import unicode_literals

import unittest2
from packaging.version import Version

from pulp_smash import cli, config, selectors, utils
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


class SyncV2TestCase(_SuccessMixin, _BaseTestCase):
    """Show it is possible to sync a docker repository with a v2 registry."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry.

        This method requires Pulp 2.8 and above, and will raise a ``SkipTest``
        exception if run against an earlier version of Pulp.
        """
        super(SyncV2TestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        docker_utils.repo_create(
            cls.cfg,
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_id,
            upstream_name=_UPSTREAM_NAME,
        )
        cls.completed_proc = docker_utils.repo_sync(cls.cfg, cls.repo_id)


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
