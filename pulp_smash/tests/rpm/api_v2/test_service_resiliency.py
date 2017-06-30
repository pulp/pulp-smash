# coding=utf-8
"""Test the resiliency of Pulp's services.

Pulp is designed to be resilient. It should be possible for a service to
disappear and reappear, with the only consequence being slower processing of
tasks. This module has tests for Pulp's resilience in the face of such issues.
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    PULP_SERVICES,
    REPOSITORY_PATH,
    RPM_MIRRORLIST_LARGE,
    RPM_UNSIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo

_PULP_WORKERS_CFG = '/etc/default/pulp_workers'


class MissingWorkersTestCase(unittest.TestCase):
    """Test that Pulp deals well with missing workers.

    When executed, this test case will do the following:

    1. Ensure there is only one Pulp worker.
    2. Create a repository. Let its feed reference a large repository. (For
       example, EPEL.)
    3. Start a sync. Immediately restart the ``pulp_workers`` service. (It's
       important that ``pulp_workers`` be restarted, not started and stopped.
       For details, see `Pulp #2835`_.) This should cause the first sync to
       abort.
    4. Update the repository. Let its feed reference a small repository. (For
       example, :data:`pulp_smash.constants.RPM_UNSIGNED_FEED_URL`.)
    5. Start a sync. Verify that it completes. If `Pulp #2835`_ still affects
       Pulp, then the worker will be broken, and the sync will never start.

    .. _Pulp #2835: https://pulp.plan.io/issues/2835
    """

    def setUp(self):
        """Ensure there is only one Pulp worker."""
        self.cfg = config.get_config()
        if selectors.bug_is_untestable(2835, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2835')
        sudo = '' if utils.is_root(self.cfg) else 'sudo'
        cli.Client(self.cfg).machine.session().run(
            "{} bash -c 'echo PULP_CONCURRENCY=1 >> {}'"
            .format(sudo, _PULP_WORKERS_CFG)
        )
        cli.GlobalServiceManager(self.cfg).restart(PULP_SERVICES)

    def test_all(self):
        """Test that Pulp deals well with missing workers."""
        # Create a repository. No repository addCleanup is necessary, because
        # Pulp will be reset after this test.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed_url'] = RPM_MIRRORLIST_LARGE
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        repo = client.get(repo['_href'], params={'details': True})

        # Start syncing the repository and restart pulp_workers.
        client.response_handler = api.code_handler
        client.post(urljoin(repo['_href'], 'actions/sync/'))
        cli.GlobalServiceManager(self.cfg).restart(('pulp_workers',))

        # Update and sync the repository.
        client.response_handler = api.safe_handler
        client.put(repo['_href'], {
            'importer_config': {'feed': RPM_UNSIGNED_FEED_URL},
        })
        utils.sync_repo(self.cfg, repo)

    def tearDown(self):
        """Reset the number of Pul pworkers, and reset Pulp.

        Reset Pulp because :meth:`test_all` may break Pulp.
        """
        sudo = () if utils.is_root(self.cfg) else ('sudo',)
        # Delete last line from file.
        cli.Client(self.cfg).run(sudo + ('sed', '-i', '$d', _PULP_WORKERS_CFG))
        utils.reset_pulp(self.cfg)
