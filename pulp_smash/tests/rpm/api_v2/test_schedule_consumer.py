# coding=utf-8
"""Test that verify scheduled RPM installation and un-installation."""
import datetime
import random
import time
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, exceptions, selectors, utils
from pulp_smash.constants import (
    CONSUMERS_PATH,
    REPOSITORY_PATH,
    RPM_UNSIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

REQUIRED_SERVICES = ('goferd',)

REQUIRED_PACKAGES = (
    'pulp-agent',
    'pulp-consumer-client',
    'pulp-rpm-consumer-extensions',
    'pulp-rpm-handlers',
    'pulp-rpm-yumplugins',
    'python-gofer-qpid',
)


class ScheduledTaskConsumer(unittest.TestCase):
    """Verify scheduled RPM installation and un-installation work.

    Test the installation and un-installation of scheduled package in a
    consumer.
    This test case targets:
    * `Pulp #2680 <https://pulp.plan.io/issues/2680>`_
    * `Pulp Smash #611 <https://github.com/PulpQE/pulp-smash/issues/611>`_
    """

    def setUp(self):
        """Install required packages and start the ``goferd`` service.

        This is done because ``goferd`` must be running in order to communicate
        with ``pulp-consumer-client``.
        """
        self.cfg = config.get_config()
        if selectors.bug_is_untestable(2680, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2680')
        self.pkg_not_installed = []
        cli_client = cli.Client(self.cfg)
        for package in REQUIRED_PACKAGES:
            try:
                cli_client.run(('rpm', '-q', package))
            except exceptions.CalledProcessError:
                self.pkg_not_installed.append(package)
        self.pkg_mgr = cli.PackageManager(self.cfg)
        if self.pkg_not_installed:
            self.pkg_mgr.install(self.pkg_not_installed)
        system = self.cfg.get_systems('shell')[0]
        self.svc_mgr = cli.ServiceManager(self.cfg, pulp_system=system)
        self.svc_mgr.start(REQUIRED_SERVICES)
        self.sudo = () if utils.is_root(self.cfg) else ('sudo',)

    def tearDown(self):
        """Remove registered consumer and stop ``goferd`` service.

        Un-install previous installed packages.
        """
        self.svc_mgr.stop(REQUIRED_SERVICES)
        cli.Client(self.cfg).run(self.sudo + (
            'pulp-consumer', '-u', self.cfg.pulp_auth[0], '-p',
            self.cfg.pulp_auth[1], 'unregister', '--force'
        ))
        if self.pkg_not_installed:
            self.pkg_mgr.uninstall(self.pkg_not_installed)

    def test_all(self):
        """Verify scheduled RPM installation and un-installation work.

        Do the following:
        1. Create a consumer, and register it.
        2. Create, sync and publish a repo.
        3. Bind the consumer to the created repo.
        4. Schedule the installation of RPM package.
        5. Schedule the un-installation of the installed package.
        """
        cli_client = cli.Client(self.cfg)

        # Create and register a consumer.
        consumer_id = utils.uuid4()
        cli_client.run(self.sudo + (
            'pulp-consumer', '-u', self.cfg.pulp_auth[0], '-p',
            self.cfg.pulp_auth[1], 'register', '--consumer-id', consumer_id
        ))

        # Create, sync and publish a repository.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(self.cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        utils.publish_repo(self.cfg, repo)

        # Bind the consumer.
        client.post(urljoin(CONSUMERS_PATH, consumer_id + '/bindings/'), {
            'distributor_id': repo['distributors'][0]['id'],
            'notify_agent': True,
            'repo_id': repo['id'],
        })

        # Schedule the installation of a random package.
        unit_name = random.choice(
            utils.search_units(self.cfg, repo, {'type_ids': ('rpm',)})
        )['metadata']['name']
        client.post(
            urljoin(
                CONSUMERS_PATH,
                consumer_id + '/schedules/content/install/'
            ),
            {
                'enabled': True,
                'failure_threshold': None,
                'schedule': self.get_iso_time_delay(5),
                'units': [{'type_id': 'rpm', 'unit_key': {'name': unit_name}}],
            }
        )

        # Wait for the package to be installed. Verify that it's present.
        time.sleep(30)
        with self.subTest('scheduled installation'):
            cmd = cli_client.run(('rpm', '-q', unit_name))
            self.assertEqual(cmd.returncode, 0)

        # Schedule un-installation of the same package.
        client.post(urljoin(
            CONSUMERS_PATH, consumer_id + '/schedules/content/uninstall/'), {
                'units': [{
                    'unit_key': {'name': unit_name},
                    'type_id': 'rpm'
                }],
                'failure_threshold': None,
                'enabled': True,
                'schedule': self.get_iso_time_delay(5)})

        # Wait for the package to be un-installed. Verify that it's absent.
        time.sleep(30)
        with self.subTest('scheduled un-installation'):
            with self.assertRaises(exceptions.CalledProcessError):
                cli_client.run(('rpm', '-q', unit_name))

    @staticmethod
    def get_iso_time_delay(delay):
        """Convert time format to ``ISO8601`` using UTC as reference.

        Besides that, add ``delay`` in seconds.
        """
        current_time_utc = datetime.datetime.utcnow()
        schedule_time = current_time_utc + datetime.timedelta(seconds=delay)
        iso_timestamp = schedule_time.isoformat()
        return 'R1/{}Z/PT1H'.format(iso_timestamp)
