# coding=utf-8
"""Common utilities that assist in testing the CLI with docker repositories."""
from __future__ import unicode_literals

import unittest2

from pulp_smash import cli, config, constants, utils


def copy(server_config, unit_type, src_repo_id, dest_repo_id):
    """Use pulp-admin to copy content from one docker repository to another.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server targeted by this function.
    :param unit_type: The type of content to copy, such as "image" or
        "manifest." Run ``pulp-admin docker repo copy --help`` to get the full
        set of available unit types.
    :param src_repo_id: A value for the ``--from-repo-id`` option.
    :param src_repo_id: A value for the ``--to-repo-id`` option.
    """
    cmd = 'pulp-admin docker repo copy {} --from-repo-id {} --to-repo-id {}'
    cmd = cmd.format(unit_type, src_repo_id, dest_repo_id).split()
    return cli.Client(server_config, cli.echo_handler).run(cmd)


def create_repo(
        server_config,
        repo_id,
        upstream_name=None,
        sync_v1=False,
        sync_v2=False):
    """Use pulp-admin to create a repo with the given parameters.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server targeted by this function.
    :param repo_id: A value for the ``--repo-id`` option.
    :param upstream_name: A value for the ``--upstream-name`` option.
    :param sync_v1: A value for the ``--enable-v1`` option.
    :param sync_v2: A value for the ``--enable-v2`` option.
    """
    extra_flags = ''
    if upstream_name:
        extra_flags += ' --upstream-name {}'.format(upstream_name)

    # Handle whether we are syncing, and if so which APIs
    if sync_v1 or sync_v2:
        # The Docker v2 feed URL can do Docker v1 as well
        extra_flags += ' --feed {}'.format(constants.DOCKER_V2_FEED_URL)
    if sync_v1:
        extra_flags += ' --enable-v1 true'
    else:
        extra_flags += ' --enable-v1 false'
    if sync_v2:
        extra_flags += ' --enable-v2 true'
    else:
        extra_flags += ' --enable-v2 false'

    command = 'pulp-admin docker repo create --repo-id {}{}'
    command = command.format(repo_id, extra_flags).split()
    return cli.Client(server_config, cli.echo_handler).run(command)


def delete_repo(server_config, repo_id):
    """Delete the repo given by repo_id."""
    cmd = 'pulp-admin docker repo delete --repo-id {}'.format(repo_id).split()
    return cli.Client(server_config, cli.echo_handler).run(cmd)


def search(server_config, unit_type, repo_id, fields=None):
    """
    Search the given repo for all units of given unit_type.

    unit_type should be a string: "image", "blob", "manifest", or "tag".
    repo_id is the repo_id you wish to search.
    fields is a list of strings of field names you want to retrieve.
    """
    extra_flags = ''
    if fields:
        extra_flags += ' --fields {}'.format(','.join(fields))
    cmd = 'pulp-admin docker repo search {} --repo-id {}{}'
    cmd = cmd.format(unit_type, repo_id, extra_flags).split()
    return cli.Client(server_config, cli.echo_handler).run(cmd)


def sync_repo(server_config, repo_id):
    """Synchronize the given repo."""
    return cli.Client(server_config, cli.echo_handler).run(
        'pulp-admin docker repo sync run --repo-id {}'.format(repo_id).split()
    )


class BaseTestCase(unittest2.TestCase):
    """A base class for testing Docker content. It logs in for you."""

    @classmethod
    def setUpClass(cls):
        """Provide a server config and a repository ID."""
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        cmd = 'pulp-admin login -u {} -p {}'.format(*cls.cfg.auth).split()
        cli.Client(cls.cfg).run(cmd)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repository."""
        cmd = 'pulp-admin docker repo delete --repo-id {}'.format(cls.repo_id)
        cli.Client(cls.cfg).run(cmd.split())


class SuccessMixin(object):
    """Add some common assertion to test cases."""

    def test_return_code(self):
        """Assert the "sync" command has a return code of 0."""
        self.assertEqual(self.completed_proc.returncode, 0)

    def test_task_succeeded(self):
        """Assert the phrase "Task Succeeded" is in stdout."""
        self.assertIn('Task Succeeded', self.completed_proc.stdout)

    def test_task_failed(self):
        """Assert the phrase "Task Failed" is not in stdout."""
        self.assertNotIn('Task Failed', self.completed_proc.stdout)
