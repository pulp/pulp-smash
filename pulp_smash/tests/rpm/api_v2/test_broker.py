# coding=utf-8
"""Tests for Pulp's "broker reconnect" feature.

Tests for `#55 <https://github.com/PulpQE/pulp-smash/issues/55>`_:

> Pulp offers a collection of behaviors known as "reconnect support" for the
> Pulp Broker. Here are the expected behaviors:
>
> * If you start a Pulp service that connects to the broker and the broker is
>   not running or is not network accessible for some reason, the Pulp services
>   will wait-and-retry. It has a backoff behavior, but the important part is
>   that Pulp services don't exit if they can't connect due to availability,
>   and when the availability problem is resolved, the Pulp services reconnect.
> * If you have a Pulp service connected to the broker and the broker shuts
>   down, the Pulp services need the wait-and-retry as described above. Once
>   the broker becomes available again the Pulp services should reconnect.

There are two scenarios to test here:

* support for initially connecting to a broker, and
* support for reconnecting to a broker that goes missing.

Both scenarios are executed by
:class:`pulp_smash.tests.rpm.api_v2.test_broker.BrokerTestCase`.
"""
from __future__ import unicode_literals

import time

import unittest2

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import (
    PULP_SERVICES,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
    RPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class BrokerTestCase(unittest2.TestCase):
    """Test Pulp's support for broker connections and reconnections."""

    def setUp(self):
        """Provide a server config and Pulp services to stop and start."""
        self.cfg = config.get_config()
        self.broker = utils.get_broker(self.cfg)
        self.services = tuple((
            cli.Service(self.cfg, service) for service in PULP_SERVICES
        ))

    def tearDown(self):
        """Ensure Pulp services and AMQP broker are running.

        Stop all relevant services, then start them again. This approach is
        slow, but see `when broker reconnect test fails, all following tests
        fail <https://github.com/PulpQE/pulp-smash/issues/91>`_.
        """
        services = self.services + (self.broker,)
        for service in services:
            service.stop()
        for service in services:
            service.start()

    def test_broker_connect(self):
        """Test Pulp's support for initially connecting to a broker.

        Do the following:

        1. Stop both the broker and several other services.
        2. Start the several other resources, wait, and start the broker.
        3. Test Pulp's health. Create an RPM repository, sync it, add a
           distributor, publish it, and download an RPM.
        """
        # Step 1 and 2.
        for service in self.services + (self.broker,):
            service.stop()
        for service in self.services:
            service.start()
        time.sleep(15)  # Let services try to connect to the dead broker.
        self.broker.start()
        self.health_check()  # Step 3.

    def test_broker_reconnect(self):
        """Test Pulp's support for reconnecting to a broker that goes missing.

        Do the following:

        1. Start both the broker and several other services.
        2. Stop the broker, wait, and start it again.
        3. Test Pulp's health. Create an RPM repository, sync it, add a
           distributor, publish it, and download an RPM.
        """
        if selectors.bug_is_untestable(1635, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1635')
        # We assume that the broker and other services are already running. As
        # a result, we skip step 1 and go straight to step 2.
        self.broker.stop()
        time.sleep(30)
        self.broker.start()
        self.health_check()  # Step 3.

    def health_check(self):
        """Execute step three of the test plan."""
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(api.Client(self.cfg).delete, repo['_href'])
        utils.sync_repo(self.cfg, repo['_href'])
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
        pulp_rpm = client.get(url).content

        # Does this RPM match the original RPM?
        rpm = utils.http_get(RPM_URL)
        self.assertEqual(rpm, pulp_rpm)
