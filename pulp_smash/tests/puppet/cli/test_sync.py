# coding=utf-8
"""Tests that sync Puppet repositories."""
import unittest

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


class SyncDownloadedContentTestCase(unittest.TestCase):
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


class SyncFromPuppetForgeTestCase(unittest.TestCase):
    """Test whether one can sync modules from the Puppet Forge.

    According to `Pulp #1846`_, Pulp sometimes fails to sync modules available
    on the Puppet forge. There is no consistency regarding which modules fail
    to sync: according to one comment, Pulp only detects 40 modules (of
    ~1,800), and according to another comment, Pulp syncs 4,089 of 4,128
    modules.

    How do we test this? The ideal test case is to repeatedly sync the entire
    Puppet Forge and check for sync failures, until the probability of another
    random failure is low. This is problematic: we're abusing the Puppet Forge
    and extending the test time. A more realistic test is to sync a small
    number of modules and ensure that no errors occur. This provides much less
    assurance, but it does at least show that *a* sync from the Puppet Forge
    can complete.

    :mod:`pulp_smash.tests.puppet.api_v2.test_sync_publish` already syncs from
    the Puppet Forge, but `Pulp #1846`_ specifically uses the CLI.

    The end result is a test case that syncs an unknown number of Puppet
    modules and which provides only minimal assurance that syncs from the
    Puppet Forge work. Unfortunately, we cannot do better.

    .. _Pulp #1846: https://pulp.plan.io/issues/1846
    """

    def test_sync_puppet_forge(self):
        """Create a Puppet repository and trigger a sync."""
        cfg = config.get_config()
        utils.pulp_admin_login(cfg)

        # Create a repository and schedule it for deletion.
        repo_id = utils.uuid4()
        client = cli.Client(cfg)
        cmd = (
            'pulp-admin puppet repo create --repo-id {} --feed {} --queries {}'
        ).format(repo_id, PUPPET_FEED, PUPPET_QUERY)
        client.run(cmd.split())
        cmd = 'pulp-admin puppet repo delete --repo-id {}'.format(repo_id)
        self.addCleanup(client.run, cmd.split())

        # Sync the repository.
        cmd = 'pulp-admin puppet repo sync run --repo-id {}'.format(repo_id)
        completed_proc = client.run(cmd.split())

        # Verify no errors were reported.
        phrase = 'Invalid properties:'
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn(phrase, getattr(completed_proc, stream))
