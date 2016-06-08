# coding=utf-8
"""Tests to verify Puppet syncs function correctly."""
from __future__ import unicode_literals

import unittest2

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import PUPPET_FEED, PUPPET_QUERY
from pulp_smash.tests.puppet.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def get_num_units_in_repo(server_config, repo_id):
    """Tell how many puppet modules are in a repository.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param repo_id: A Puppet repository ID.
    :returns: The number of puppet modules in a repository, as an ``int``.
    """
    keyword = 'Puppet Module:'
    completed_proc = cli.Client(server_config).run((
        'pulp-admin puppet repo list --repo-id {} --fields content_unit_counts'
    ).format(repo_id).split())
    lines = [
        line for line in completed_proc.stdout.splitlines() if keyword in line
    ]
    # If puppet modules are present, a "Puppet Module: n" line is printed.
    # Otherwise, nothing is printed.
    assert len(lines) in (0, 1)
    if len(lines) == 0:
        return 0
    else:
        return int(lines[0].split(keyword)[1].strip())


class SyncDownloadedContentTestCase(unittest2.TestCase):
    """Test whether Pulp can associate already-downloaded content with a repo.

    Consider the following scenario:

    1. Create a repository with a feed and sync it.
    2. Create a second repository with the same feed and sync it.

    When the second repository is synced, Pulp should recognize that the needed
    content units are already present, and it should associate them with the
    second repository. However, according to `Pulp #1937`_, Pulp fails to do
    this, and the second repository will not be populated.

    This test case tests `Pulp #1937`_ and the corresponding Pulp Smash issue,
    `Pulp Smash #269`_.

    .. _NOTE: The first repository may be populated through any means
        available, including direct uploads.

    .. _Pulp #1937: https://pulp.plan.io/issues/1937
    .. _Pulp Smash #269: https://github.com/PulpQE/pulp-smash/issues/269
    """

    def test_sync_downloaded_content(self):
        """Create two repositories with the same feed, and sync them serially.

        More specifically, this test creates two puppet repositories with
        identical feeds, syncs them serially, and verifies that both have equal
        non-zero content unit counts.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(1937, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1937')
        utils.pulp_admin_login(cfg)

        # Create two repos, schedule them for deletion, and sync them.
        client = cli.Client(cfg)
        repo_ids = [utils.uuid4() for _ in range(2)]
        for repo_id in repo_ids:
            client.run((
                'pulp-admin puppet repo create '
                '--repo-id {} --feed {} --queries {}'
            ).format(repo_id, PUPPET_FEED, PUPPET_QUERY).split())
            self.addCleanup(client.run, (
                'pulp-admin puppet repo delete --repo-id {}'
            ).format(repo_id).split())
            client.run((
                'pulp-admin puppet repo sync run --repo-id {}'
            ).format(repo_id).split())

        # Verify the number of puppet modules in each repository.
        unit_counts = [
            get_num_units_in_repo(cfg, repo_id) for repo_id in repo_ids
        ]
        for i, unit_count in enumerate(unit_counts):
            with self.subTest(i=i):
                self.assertGreater(unit_count, 0)
        self.assertEqual(unit_counts[0], unit_counts[1])
