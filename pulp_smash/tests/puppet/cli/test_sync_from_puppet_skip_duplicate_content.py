# coding=utf-8
"""Tests that to verify Puppet sync on duplicate contents."""
from __future__ import unicode_literals

import unittest2

from pulp_smash import cli, config, utils
from pulp_smash.constants import PUPPET_FEED, PUPPET_QUERY
from pulp_smash.tests.puppet.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class SyncFromPuppetSkipDuplicateContentTestCase(unittest2.TestCase):
    """Test whether the importer recognizes the content already in Pulp.

    According to `Pulp #1937`_, Pulp sometimes fails to sync units into a
    repository if the unit already existed.

    How do we test this? The test steps would be as follows:

    1. upload or sync a module to repo1
    2. perform a sync on repo2 against a forge-style repository
       (one with a modules.json file) that includes the module from 1.
    3. Assert the module from 1. is in the published repo2.
       (i.e., check if the they have identical counts of content units)

    Please see reference from: https://github.com/PulpQE/pulp-smash/issues/269

    The end result is a test case that syncs an existing Puppet modules
    into two repositories and check whether the 2nd would have same amount
    of content units with the 1st.

    .. _Pulp #1937: https://pulp.plan.io/issues/1937

    """

    def test_sync_puppet_forge(self):
        """Create two Puppet repositories and trigger their syncs."""
        cfg = config.get_config()
        utils.pulp_admin_login(cfg)

        # Create two different repositories and schedule them for syncs.
        repo_ids = [utils.uuid4() for _ in range(2)]
        client = cli.Client(cfg)

        for repo_id in repo_ids:
            # Create the repository.
            cmd = (
                'pulp-admin puppet repo create '
                '--repo-id {} --feed {} --queries {}'
            ).format(repo_id, PUPPET_FEED, PUPPET_QUERY)
            client.run(cmd.split())

            # Delete the repository.
            cmd = 'pulp-admin puppet repo delete --repo-id {}'.format(repo_id)
            self.addCleanup(client.run, cmd.split())

            # Sync the repository.
            cmd = (
                'pulp-admin puppet repo sync run --repo-id {}'
            ).format(repo_id)
            client.run(cmd.split())

        # Verify that all the repositories have an identical non-zero
        # number of content units present with the 1st one
        first_repo_counts = get_content_counts_by_repo_id(repo_ids[0], cfg)
        self.assertIsNot(first_repo_counts, 0, 'Counts should be non-zero.')
        for repo_id in repo_ids:
            # Compute current repository's content unit counts
            if repo_id is not repo_ids[0]:
                counts = get_content_counts_by_repo_id(repo_id, cfg)
                self.assertIsNot(counts, 0, 'Counts should be non-zero.')
                self.assertEqual(
                    first_repo_counts,
                    counts,
                    'The numbers of content units are not equal.'
                )


def get_content_counts_by_repo_id(repo_id, server_config):
    """Tell how many puppet modules are in a repository.

    :param repo_id: A Puppet repository ID.
    :param  pulp_smash.config.ServerConfig server_config: Information
        about the Pulp server being targeted.
    :returns: The number of puppet modules in a repository, as an ``int``.
    """
    keyword = 'Puppet Module:'
    completed_proc = cli.Client(server_config).run((
        'pulp-admin puppet repo list --repo-id {} '
        '--fields content_unit_counts'
    ).format(repo_id).split())
    lines = [
        line for line in completed_proc.stdout.splitlines()
        if keyword in line
    ]
    # If the puppet modules exist, a "Puppet Module: n" line is printed.
    # Otherwise, nothing is printed.
    assert len(lines) in (0, 1)
    if len(lines) == 0:
        return 0
    else:
        return int(lines[0].split(keyword)[1].strip())
