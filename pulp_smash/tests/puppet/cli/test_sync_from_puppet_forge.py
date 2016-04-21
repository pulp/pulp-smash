# coding=utf-8
"""Tests that CRUD Puppet repositories."""
from __future__ import unicode_literals

import unittest2

from pulp_smash import cli, config, utils
from pulp_smash.constants import PUPPET_FEED, PUPPET_QUERY
from pulp_smash.tests.puppet.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class SyncFromPuppetForgeTestCase(unittest2.TestCase):
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
