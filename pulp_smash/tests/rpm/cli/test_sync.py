# coding=utf-8
"""Tests that sync RPM repositories."""
from __future__ import unicode_literals

import random

import unittest2

from pulp_smash import cli, config, utils
from pulp_smash.constants import RPM_FEED_URL
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login`` on the target Pulp system."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


def get_rpm_names(server_config, repo_id):
    """Get a list of names of all packages in a repository.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param repo_id: A RPM repository ID.
    :returns: The names of all modules in a repository, as an ``list``.
    """
    keyword = 'Name:'
    completed_proc = cli.Client(server_config).run(
        'pulp-admin rpm repo content rpm --repo-id {}'.format(repo_id).split()
    )
    return [
        line.split(keyword)[1].strip()
        for line in completed_proc.stdout.splitlines() if keyword in line
    ]


def sync_repo(server_config, repo_id):
    """Sync an RPM repository.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param repo_id: A RPM repository ID.
    :returns: A :class:`pulp_smash.cli.CompletedProcess`.
    """
    return cli.Client(server_config).run(
        'pulp-admin rpm repo sync run --repo-id {}'.format(repo_id).split()
    )


class RemovedContentTestCase(unittest2.TestCase):
    """Test whether Pulp can sync content into a repo after it's been removed.

    This test case targets `Pulp #1775`_ and the corresponding Pulp Smash
    issue, `Pulp Smash #243`_.

    1. Create and sync a repository. Select a content unit.
    2. Delete the content unit from the repository, and verify it's absent.
    3. Sync the repository, and verify that the content unit is present.

    .. _Pulp #1775: https://pulp.plan.io/issues/1775
    .. _Pulp Smash #243: https://github.com/PulpQE/pulp-smash/issues/243
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository. Select a content unit from it."""
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        cli.Client(cls.cfg).run(
            'pulp-admin rpm repo create --repo-id {} --feed {}'
            .format(cls.repo_id, RPM_FEED_URL).split()
        )
        sync_repo(cls.cfg, cls.repo_id)
        cls.rpm_name = random.choice(get_rpm_names(cls.cfg, cls.repo_id))

    def test_01_remove_rpm(self):
        """Remove the selected RPM from the repository. Verify it's absent."""
        cli.Client(self.cfg).run(
            'pulp-admin rpm repo remove rpm --repo-id {} --str-eq name={}'
            .format(self.repo_id, self.rpm_name).split()
        )
        self.assertNotIn(self.rpm_name, get_rpm_names(self.cfg, self.repo_id))

    def test_02_add_rpm(self):
        """Sync the repository. Verify the selected RPM is present."""
        completed_proc = sync_repo(self.cfg, self.repo_id)
        with self.subTest():
            self.assertIn(self.rpm_name, get_rpm_names(self.cfg, self.repo_id))
        phrase = 'Invalid properties:'
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn(phrase, getattr(completed_proc, stream))

    @classmethod
    def tearDownClass(cls):
        """Delete the repository and clean up orphans."""
        cli.Client(cls.cfg).run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
