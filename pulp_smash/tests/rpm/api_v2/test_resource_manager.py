# coding=utf-8
"""Tests for pulp_resource_manager failover scenarios."""
from __future__ import unicode_literals

import time
import shlex
import unittest2

from pulp_smash import api, cli, config, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import (
    PULP_SERVICES,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
    RPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_status
)
from pulp_smash.tests.rpm.utils import set_up_module  # noqa pylint:disable=unused-import


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests if there is no system available for failover testing."""
    set_up_module()
    if 'pulp failover test' not in config.ServerConfig().sections():
        raise unittest2.SkipTest(
            'This module requires a system available for failover testing'
        )


class ResourceManagerTest(unittest2.TestCase):
    """Test multi-machine pulp_resource_manager failover functonality."""

    @classmethod
    def setUpClass(cls):
        """Create handles for common resources."""
        cls.cfgs = {
            'box1': config.ServerConfig().read(section='pulp'),
            'box2': config.ServerConfig().read(section='pulp failover test')
        }

        box1_services = {}
        box2_services = {}

        for service in PULP_SERVICES:
            box1_services[service] = \
                cli.Service(cls.cfgs['box1'], service)

        box2_services['pulp_resource_manager'] = \
            cli.Service(cls.cfgs['box2'], 'pulp_resource_manager')

        cls.services = {
            'box1': box1_services,
            'box2': box2_services
        }

        cls.broker = utils.get_broker(cls.cfgs['box1'])

    @classmethod
    def tearDownClass(cls):
        """Put everything back into the normal one-box configuration."""
        for _, service in cls.services['box2'].items():
            service.stop()
        time.sleep(5)
        for _, service in cls.services['box1'].items():
            service.start()
        time.sleep(5)

    def setUp(self):
        """Start all services on box 1, stop all services on box 2."""
        for _, service in self.services['box2'].items():
            service.stop()
        time.sleep(5)
        for _, service in self.services['box1'].items():
            service.start()
        time.sleep(5)

    def sync_and_publish(self, server_config):
        """Test Pulp's health.

        Create an RPM repository, sync it, add a distributor, publish it, and
        download an RPM.  Returns the name of the worker that the task was
        executed on

        Slightly different from pulp_smash.test.rpm.api_v2.utils.health_check

        :param pulp_smash.config.ServerConfig server_config: Information about
            the Pulp server being targeted.
        """
        client = api.Client(server_config, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        call_report = utils.sync_repo(server_config, repo['_href']).json()
        distributor = client.post(
            urljoin(repo['_href'], 'distributors/'),
            gen_distributor(),
        )
        client.post(
            urljoin(repo['_href'], 'actions/publish/'),
            {'id': distributor['id']},
        )
        client.response_handler = api.safe_handler
        url = urljoin('/pulp/repos/', distributor['config']['relative_url'])
        url = urljoin(url, RPM)

        # Does this RPM match the original RPM?
        pulp_rpm = client.get(url).content
        rpm = utils.http_get(RPM_URL)
        api.Client(server_config).delete(repo['_href'])

        self.assertEqual(rpm, pulp_rpm)

        last_task = next(api.poll_spawned_tasks(self.cfgs['box1'],
                                                call_report))

        self.assertEqual('finished', last_task['state'])
        self.assertEqual(None, last_task['error'])

        return last_task['worker_name']

    def test_failover_on_sigterm(self):
        """Test resource manager failover with the SIGTERM signal.

        Tests that starting two resource managers and terminating the
        active resource manager will properly fail over to the second resource
        manager.
        """
        # Check that exactly 1 resource manager is running
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(1, return_text.count('resource_manager'))

        # Start a 2nd resource manager on box 2
        self.services['box2']['pulp_resource_manager'].start()
        time.sleep(5)

        # Check that both show up in the API
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(2, return_text.count('resource_manager'))

        # Create sync and publish tasks
        worker_name1 = self.sync_and_publish(self.cfgs['box1'])
        time.sleep(10)

        # Stop the active resource manager on box 1, wait long enough for the
        # failover to occur, attempt a sync and ensure that it succeeded
        self.services['box1']['pulp_resource_manager'].stop()
        time.sleep(90)
        worker_name2 = self.sync_and_publish(self.cfgs['box1'])

        # Check that both tasks were run on the same worker
        self.assertEqual(worker_name1, worker_name2)

        # Stop the remaining resource manager
        self.services['box2']['pulp_resource_manager'].stop()
        time.sleep(5)

        # Check that no resource managers are running
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(0, return_text.count('resource_manager'))

        # Start one resource manager back up
        self.services['box2']['pulp_resource_manager'].start()
        time.sleep(5)

        # Check that exactly 1 resource manager is running
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(1, return_text.count('resource_manager'))

        # Attempt another sync and ensure that it was successful
        self.sync_and_publish(self.cfgs['box1'])

    def test_failover_on_sigkill(self):
        """Test resource manager failover with the SIGKILL signal.

        Tests that starting two resource managers and hard-killing the
        active resource manager will properly fail over to the second resource
        manager.
        """
        # Check that exactly 1 resource manager is running
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(1, return_text.count('resource_manager'))

        # Start a 2nd resource manager on box 2
        self.services['box2']['pulp_resource_manager'].start()
        time.sleep(5)

        # Check that both show up in the API
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(2, return_text.count('resource_manager'))

        # Create sync and publish tasks
        worker_name1 = self.sync_and_publish(self.cfgs['box1'])
        time.sleep(10)

        # Stop the active resource manager on box 1, wait long enough for the
        # failover to occur, attempt a sync and ensure that it succeeded
        pids = cli.Client(self.cfgs['box1']).run(
            shlex.split('pgrep -f resource_manager')).stdout
        pids = pids.split()[:-1]
        pids = ' '.join(pids)
        cli.Client(self.cfgs['box1']).run(shlex.split('sudo kill -9 ' + pids))
        time.sleep(300)
        worker_name2 = self.sync_and_publish(self.cfgs['box1'])

        # Check that both tasks were run on the same worker
        self.assertEqual(worker_name1, worker_name2)

        # Stop the remaining resource manager
        self.services['box2']['pulp_resource_manager'].stop()
        time.sleep(5)

        # Check that no resource managers are running
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(0, return_text.count('resource_manager'))

        # Start one resource manager back up
        self.services['box2']['pulp_resource_manager'].start()
        time.sleep(5)

        # Check that exactly 1 resource manager is running
        return_text = get_status(self.cfgs['box1']).text
        self.assertEqual(1, return_text.count('resource_manager'))

        # Attempt another sync and ensure that it was successful
        self.sync_and_publish(self.cfgs['box1'])
