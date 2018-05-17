# coding=utf-8
"""Tests for syncing and publishing docker repositories."""
from pulp_smash import cli, config, selectors, utils
from pulp_smash.pulp2.utils import BaseAPITestCase, pulp_admin_login
from pulp_smash.tests.pulp2.docker.cli.utils import repo_create, repo_delete
from pulp_smash.tests.pulp2.docker.utils import (
    get_upstream_name,
    set_up_module,
)


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login``."""
    set_up_module()
    pulp_admin_login(config.get_config())


class InvalidFeedTestCase(BaseAPITestCase):
    """Show Pulp behaves correctly when syncing a repo with an invalid feed."""

    def test_all(self):
        """Create a docker repo with an invalid feed and sync it."""
        repo_id = utils.uuid4()
        self.assertNotIn('Task Failed', repo_create(
            self.cfg,
            feed='https://docker.example.com',
            repo_id=repo_id,
            upstream_name=get_upstream_name(self.cfg),
        ).stdout)
        self.addCleanup(repo_delete, self.cfg, repo_id)
        client = cli.Client(self.cfg, cli.echo_handler)
        proc = client.run((
            'pulp-admin', 'docker', 'repo', 'sync', 'run', '--repo-id', repo_id
        ))
        if selectors.bug_is_testable(427, self.cfg.pulp_version):
            with self.subTest():
                self.assertNotEqual(proc.returncode, 0)
        with self.subTest():
            self.assertNotIn('Task Succeeded', proc.stdout)
        with self.subTest():
            self.assertIn('Task Failed', proc.stdout)
