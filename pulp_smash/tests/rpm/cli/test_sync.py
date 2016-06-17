# coding=utf-8
"""Tests that sync RPM repositories."""

from __future__ import unicode_literals

import random
import unittest2

from pulp_smash import cli, config, utils
from pulp_smash.constants import RPM_FEED_URL
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def get_content_names(server_config, repo_id):
    """Get a list of names of all packages in a repository.

    :param server_config: Information about the Pulp server being targeted.
    :param repo_id: A RPM repository ID.
    :type server_config: pulp_smash.config.ServerConfig.
    :returns: The names of all modules in a repository, as an ``list``.
    """
    keyword = 'Name:'
    completed_proc = cli.Client(server_config).run(
        'pulp-admin rpm repo content rpm --repo-id {}'.format(repo_id).split()
    )
    lines = [
        line.split(keyword)[1].strip()
        for line in completed_proc.stdout.splitlines() if keyword in line
    ]
    return lines


class RemovedContentTestCase(unittest2.TestCase):
    """Test whether Pulp can restore already-removed content with a repo.

    This test case tests `Pulp #1775`_ and the corresponding Pulp Smash issue,
    `Pulp Smash #243`_.

    The test steps are as following:

    1. Create a repository and synchronize it.
    2. Remove some rpm package from the repository.
    3. Sync again and check that the removed units are back.

    .. _Pulp #1775: https://pulp.plan.io/issues/1775
    .. _Pulp Smash #243: https://github.com/PulpQE/pulp-smash/issues/243
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository."""
        cls.cfg = config.get_config()
        cls.client = cli.Client(cls.cfg)
        cls.repo_id = utils.uuid4()
        cls.client.run(
            'pulp-admin rpm repo create --repo-id {0} --feed {1}'
            .format(cls.repo_id, RPM_FEED_URL).split()
        )

    def test_remove_then_resync(self):
        """Remove a package from repository and then re-sync."""
        self.sync_rpm_repo()
        # Get a list of all rpm content names.
        rpm_names = get_content_names(self.cfg, self.repo_id)
        # Select a random content name and remove it.
        target_rpm = random.choice(rpm_names)
        self.client.run(
            'pulp-admin rpm repo remove rpm --repo-id {} --str-eq name={}'
            .format(self.repo_id, target_rpm).split()
        )
        # Check whether that RPM package is deleted.
        with self.subTest():
            self.assertNotIn(
                target_rpm,
                get_content_names(self.cfg, self.repo_id),
                'The RPM {} should have been deleted.'.format(target_rpm)
            )
        # Re-sync the repository.
        self.sync_rpm_repo()
        # Check whether that RPM package is restored.
        with self.subTest():
            self.assertIn(
                target_rpm,
                get_content_names(self.cfg, self.repo_id),
                'The RPM {} should have been restored.'.format(target_rpm)
            )

    def sync_rpm_repo(self):
        """Sync or Re-sync the RPM repository."""
        completed_proc = cli.Client(self.cfg).run((
            'pulp-admin rpm repo sync run --repo-id {}'
        ).format(self.repo_id).split())
        # Verify no errors were reported.
        phrase = 'Invalid properties:'
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn(phrase, getattr(completed_proc, stream))

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
