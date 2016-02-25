# coding=utf-8
"""CRUD tests for docker repositories.

These tests can also be accomplished via the API. However, there is value in
showing that the pulp-admin CLI client correctly interfaces with the API.
"""
from __future__ import unicode_literals
import re

import unittest2
from packaging import version

from pulp_smash import cli, config, selectors, utils
from pulp_smash.tests.docker.cli import utils as docker_utils

_FEED = 'https://example.com'
_UPSTREAM_NAME = 'foo/bar'


class CreateTestCase(unittest2.TestCase):
    """Create docker repositories, both successfully and unsuccessfully."""

    def setUp(self):
        """Provide a server config and a repository ID."""
        self.cfg = config.get_config()
        self.repo_id = utils.uuid4()
        docker_utils.login(self.cfg)

    def tearDown(self):
        """Delete created resources."""
        docker_utils.repo_delete(self.cfg, self.repo_id)

    def test_basic(self):
        """Create a docker repository. Only provide a repository ID.

        Assert the return code is 0.
        """
        completed_proc = docker_utils.repo_create(
            self.cfg,
            repo_id=self.repo_id
        )
        self.assertEqual(completed_proc.returncode, 0)

    def test_with_feed_upstream_name(self):
        """Create a docker repository. Provide a feed and upstream name.

        Assert the return code is 0.
        """
        completed_proc = docker_utils.repo_create(
            self.cfg,
            feed=_FEED,
            repo_id=self.repo_id,
            upstream_name=_UPSTREAM_NAME,
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


class UpdateEnableV1TestCase(unittest2.TestCase):
    """Update a docker repository's --enable-v1 flag.

    There was a bug in pulp-admin wherein the --enable-v1 flag could be set
    during repository creation, but not while updating repositories. This test
    ensures that behavior functions correctly.
    """

    @classmethod
    def setUpClass(cls):
        """Provide a server config and a repository ID."""
        cls.cfg = config.get_config()

        if cls.cfg.version < version.Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        if selectors.bug_is_untestable(1710):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1710')

        docker_utils.login(cls.cfg)

        cls.repo_id = utils.uuid4()
        docker_utils.repo_create(
            cls.cfg,
            repo_id=cls.repo_id,
            enable_v1='false'
        )
        cls.update_response = docker_utils.repo_update(
            cls.cfg,
            repo_id=cls.repo_id,
            enable_v1='true',
        )

    @classmethod
    def tearDownClass(cls):
        """Delete created resources."""
        docker_utils.repo_delete(cls.cfg, cls.repo_id)

    def test_change_enable_v1_flag(self):
        """Test that the the --enable-v1 flag was successful."""
        repo_details = docker_utils.repo_list(
            self.cfg,
            repo_id=self.repo_id,
            details=True,
        ).stdout

        # Enable V1: True should appear in the output of the repo list
        match = re.search(r'(?:Enable V1:)\s*(.*)', repo_details)
        self.assertEqual(match.group(1), 'True')

    def test_success(self):
        """Assert that the CLI reported success."""
        self.assertTrue('Task Succeeded' in self.update_response.stdout)


class UpdateEnableV2TestCase(unittest2.TestCase):
    """Update a docker repository's --enable-v2 flag.

    There was a bug in pulp-admin wherein the --enable-v2 flag could be set
    during repository creation, but not while updating repositories. This test
    ensures that behavior functions correctly.
    """

    @classmethod
    def setUpClass(cls):
        """Provide a server config and a repository ID."""
        cls.cfg = config.get_config()

        if cls.cfg.version < version.Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        if selectors.bug_is_untestable(1710):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1710')

        docker_utils.login(cls.cfg)

        cls.repo_id = utils.uuid4()
        docker_utils.repo_create(
            cls.cfg,
            repo_id=cls.repo_id,
            enable_v2='false',
        )
        cls.update_response = docker_utils.repo_update(
            cls.cfg,
            repo_id=cls.repo_id,
            enable_v2='true',
        )

    @classmethod
    def tearDownClass(cls):
        """Delete created resources."""
        docker_utils.repo_delete(cls.cfg, cls.repo_id)

    def test_change_enable_v2_flag(self):
        """Test that the the --enable-v2 flag was successful."""
        repo_details = docker_utils.repo_list(
            self.cfg,
            repo_id=self.repo_id,
            details=True
        ).stdout

        # Enable V2: True should appear in the output of the repo list
        match = re.search(r'(?:Enable V2:)\s*(.*)', repo_details)
        self.assertEqual(match.group(1), 'True')

    def test_success(self):
        """Assert that the CLI reported success."""
        self.assertTrue('Task Succeeded' in self.update_response.stdout)
