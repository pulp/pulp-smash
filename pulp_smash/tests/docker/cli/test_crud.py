# coding=utf-8
"""CRUD tests for docker repositories.

These tests can also be accomplished via the API. However, there is value in
showing that the pulp-admin CLI client correctly interfaces with the API.
"""
from __future__ import unicode_literals

import unittest2

from pulp_smash import cli, config, utils

_FEED = 'https://example.com'
_UPSTREAM_NAME = 'foo/bar'


class CreateTestCase(unittest2.TestCase):
    """Create docker repositories, both successfully and unsuccessfully."""

    def setUp(self):
        """Provide a server config and a repository ID."""
        self.cfg = config.get_config()
        self.repo_id = utils.uuid4()
        cli.Client(self.cfg).run(
            'pulp-admin login -u {} -p {}'
            .format(self.cfg.auth[0], self.cfg.auth[1]).split()
        )

    def tearDown(self):
        """Delete created resources."""
        cli.Client(self.cfg).run(
            'pulp-admin docker repo delete --repo-id {}'
            .format(self.repo_id).split()
        )

    def test_basic(self):
        """Create a docker repository. Only provide a repository ID.

        Assert the return code is 0.
        """
        completed_proc = cli.Client(self.cfg, cli.echo_handler).run(
            'pulp-admin docker repo create --repo-id {}'
            .format(self.repo_id).split()
        )
        self.assertEqual(completed_proc.returncode, 0)

    def test_with_feed_upstream_name(self):
        """Create a docker repository. Provide a feed and upstream name.

        Assert the return code is 0.
        """
        completed_proc = cli.Client(self.cfg, cli.echo_handler).run(
            'pulp-admin docker repo create '
            '--repo-id {} --feed {} --upstream-name {}'
            .format(self.repo_id, _FEED, _UPSTREAM_NAME).split()
        )
        self.assertEqual(completed_proc.returncode, 0)

    def test_duplicate_ids(self):
        """Create two docker repositories with identical IDs.

        Assert only the first repository is created.
        """
        client = cli.Client(self.cfg)
        command = 'pulp-admin docker repo create --repo-id ' + self.repo_id
        client.run(command.split())

        client.response_handler = cli.echo_handler
        self.assertNotEqual(client.run(command.split()).returncode, 0)
