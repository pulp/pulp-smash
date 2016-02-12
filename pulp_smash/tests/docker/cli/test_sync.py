# coding=utf-8
"""Tests for syncing docker repositories."""
from __future__ import unicode_literals

import unittest2
from packaging.version import Version

from pulp_smash import cli, config, selectors, utils

_CREATE_COMMAND = (
    'pulp-admin docker repo create '
    '--feed {feed} '
    '--repo-id {repo_id} '
    '--upstream-name {upstream_name} '
)
_UPSTREAM_NAME = 'library/busybox'


def _sync_repo(server_config, repo_id):
    return cli.Client(server_config, cli.echo_handler).run(
        'pulp-admin docker repo sync run --repo-id {}'.format(repo_id).split()
    )


class _BaseTestCase(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        """Provide a server config and a repository ID."""
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        cli.Client(cls.cfg).run(
            'pulp-admin login -u {} -p {}'
            .format(cls.cfg.auth[0], cls.cfg.auth[1]).split()
        )

    @classmethod
    def tearDownClass(cls):
        """Delete the created repository."""
        command = 'pulp-admin docker repo delete --repo-id {}'
        cli.Client(cls.cfg).run(command.format(cls.repo_id).split())


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
        kwargs = {
            'feed': 'https://index.docker.io',  # v1 feed
            'repo_id': cls.repo_id,
            'upstream_name': _UPSTREAM_NAME,
        }
        cli.Client(cls.cfg).run(_CREATE_COMMAND.format(**kwargs).split())
        cls.completed_proc = _sync_repo(cls.cfg, cls.repo_id)


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
        kwargs = {
            'feed': 'https://registry-1.docker.io',  # v2 feed
            'repo_id': cls.repo_id,
            'upstream_name': _UPSTREAM_NAME,
        }
        cli.Client(cls.cfg).run(_CREATE_COMMAND.format(**kwargs).split())
        cls.completed_proc = _sync_repo(cls.cfg, cls.repo_id)


class InvalidFeedTestCase(_BaseTestCase):
    """Show Pulp behaves correctly when syncing a repo with an invalid feed."""

    @classmethod
    def setUpClass(cls):
        """Create a docker repo with an invalid feed and sync it."""
        super(InvalidFeedTestCase, cls).setUpClass()
        kwargs = {
            'feed': 'https://docker.example.com',
            'repo_id': cls.repo_id,
            'upstream_name': _UPSTREAM_NAME,
        }
        cli.Client(cls.cfg).run(_CREATE_COMMAND.format(**kwargs).split())
        cls.completed_proc = _sync_repo(cls.cfg, cls.repo_id)

    def test_return_code(self):
        """Assert the "sync" command has a non-zero return code."""
        if selectors.bug_is_untestable(1637):
            self.skipTest('https://pulp.plan.io/issues/1637')
        self.assertNotEqual(self.completed_proc.returncode, 0)

    def test_task_succeeded(self):
        """Assert the phrase "Task Succeeded" is not in stdout."""
        self.assertNotIn('Task Succeeded', self.completed_proc.stdout)

    def test_task_failed(self):
        """Assert the phrase "Task Failed" is in stdout."""
        self.assertIn('Task Failed', self.completed_proc.stdout)
