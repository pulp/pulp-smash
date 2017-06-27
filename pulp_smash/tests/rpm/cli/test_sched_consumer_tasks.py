# coding=utf-8
"""Test that scheduled RPM related tasks for consumer work."""
import unittest
import datetime
import time

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import RPM_UNSIGNED_FEED_URL
from pulp_smash.tests.rpm.utils import set_up_module
from pulp_smash.utils import is_root

def setUpModule():  # pylint:disable=invalid-name
    """Execute common steps for rpm tests."""
    set_up_module()


class _BaseTestCase(unittest.TestCase):
    """Set up a repository and consumer, and clean up after."""

    @classmethod
    def setUpClass(cls):
        """Set up a repository and consumer.

        1) Reset pulp
        2) Make sure pulp consumer is not registered
        3) Create, sync, and publish a repository.
        4) Create a consumer and register it to the server
        """
        cls.cfg = config.get_config()
        try:
            pulp_consumer = cls.cfg.get_systems('pulp consumer')[0]
        except IndexError:
            raise unittest.SkipTest('No pulp consumer system found -- skipping test')
        utils.pulp_admin_login(cls.cfg)
        cls.repo_id = utils.uuid4()
        cls.client = cli.Client(cls.cfg)
        cls.consumer_id = utils.uuid4()
        cls.sudo = () if is_root(config.get_config()) else ('sudo',)
        cls.pulp_auth = config.get_config().pulp_auth

        # quietly try and unregister pulp-consumer
        cli.Client(config.get_config(), cli.echo_handler).run(
            cls.sudo + ('pulp-consumer', 'unregister', '--force',)
        )

        # Create repo
        cls.client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', cls.repo_id,
            '--feed', RPM_UNSIGNED_FEED_URL,
        ))

        # Sync repo
        cls.client.run((
            'pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id',
            cls.repo_id,
        ))

        # Publish repo
        cls.client.run((
            'pulp-admin', 'rpm', 'repo', 'publish', 'run', '--repo-id',
            cls.repo_id,
        ))

        # Create a consumer.
        cls.client.run(
            cls.sudo + ('pulp-consumer', '-u', cls.pulp_auth[0], '-p',
                        cls.pulp_auth[1], 'register', '--consumer-id',
                        cls.consumer_id,)
        )

    @classmethod
    def tearDownClass(cls):
        """Reset pulp, discarding old repos, and unregister consumer."""
        utils.reset_pulp(config.get_config())
        # quietly try and unregister pulp-consumer
        cli.Client(config.get_config(), cli.echo_handler).run(
            cls.sudo + ('pulp-consumer', 'unregister', '--force',))


class ScheduleRPMInstallTestCase(_BaseTestCase):
    """Test whether scheduled RPM install works.

    This test case targets `Pulp #2680`_ and the corresponding Pulp Smash
    issue, `Pulp Smash #611`_.

    0. Given a registered pulp-consumer, and a sync/published repo
    1. Bind the consumer to the repo
    2. Schedule the installation of an RPM package
    3. Wait until the schedule triggers
    4. Check the results

    .. _Pulp #2680: https://pulp.plan.io/issues/2680
    .. _Pulp Smash #611: https://github.com/PulpQE/pulp-smash/issues/611
    """

    def test_install(self):
        """Test whether single scheduled RPM install works."""
        if selectors.bug_is_untestable(2680, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2680')

        # Bind the consumer.
        self.client.run(
            self.sudo + ('pulp-consumer', 'rpm', 'bind', '--repo-id',
                         self.repo_id,)
        )

        #  Schedule install
        #  This requires knowing the name of one of the packages in the repo.
        #  This is hard coded in now, probably not the best
        current_time = datetime.datetime.now()
        schedule_time = current_time + datetime.timedelta(seconds=5)
        iso_timestamp = schedule_time.isoformat()
        iso_timestamp = 'R1/%sZ/PT1H' % iso_timestamp
        self.client.run((
            'pulp-admin', '-vvv', 'rpm', 'consumer', 'package', 'install',
            'schedules', 'create', '--schedule', iso_timestamp,
            '--consumer-id', self.consumer_id, '--name', 'camel'
        ))

        # Sleep until done. This is not the best way to find out of it the task
        # is complete
        time.sleep(30)

        # Check result
        self.client.run(('rpm -q camel'.split()))
        # Clean up
        self.client.run(self.sudo + ('dnf', '-y', 'remove', 'camel',))
