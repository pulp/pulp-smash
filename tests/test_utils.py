# coding=utf-8
"""Unit tests for :mod:`pulp_smash.utils`."""
from __future__ import unicode_literals

import mock
import unittest2

from pulp_smash import cli, utils


class UUID4TestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.uuid4`."""

    def test_type(self):
        """Assert the method returns a unicode string."""
        self.assertIsInstance(utils.uuid4(), type(''))


class GetBrokerTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.get_broker`."""

    def test_success(self):
        """Successfully generate a broker service management object.

        Assert that:

        * ``get_broker(…)`` returns ``Service(…)``.
        * The ``server_config`` argument is passed to the service object.
        * The "qpidd" broker is the preferred broker.
        """
        server_config = mock.Mock()
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 0
            with mock.patch.object(cli, 'Service') as service:
                broker = utils.get_broker(server_config)
        self.assertEqual(service.return_value, broker)
        self.assertEqual(service.call_args[0], (server_config, 'qpidd'))

    def test_failure(self):
        """Fail to generate a broker service management object.

        Assert that :class:`pulp_smash.utils.NoKnownBrokerError` is raised if
        the function cannot find a broker.
        """
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 1
            with self.assertRaises(utils.NoKnownBrokerError):
                utils.get_broker(mock.Mock())
