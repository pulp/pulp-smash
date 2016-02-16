# coding=utf-8
"""Unit tests for :mod:`pulp_smash.utils`."""
from __future__ import unicode_literals

import random

import mock
import unittest2

from pulp_smash import api, cli, config, exceptions, utils


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

        Assert that :class:`pulp_smash.exceptions.NoKnownBrokerError` is raised
        if the function cannot find a broker.
        """
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 1
            with self.assertRaises(exceptions.NoKnownBrokerError):
                utils.get_broker(mock.Mock())


class BaseAPITestCase(unittest2.TestCase):
    """Test :class:`pulp_smash.utils.BaseAPITestCase`."""

    @classmethod
    def setUpClass(cls):
        """Define a child class. Call setup and teardown methods on it.

        We define a child class in order to avoid altering
        :class:`pulp_smash.utils.BaseAPITestCase`. Calling class methods on it
        would do so.
        """
        class Child(utils.BaseAPITestCase):
            """An empty child class."""

            pass

        with mock.patch.object(config, 'get_config'):
            Child.setUpClass()
        for i in range(random.randint(1, 100)):
            Child.resources.add(i)

        # Make class available to test methods
        cls.child = Child

    def test_set_up_class(self):
        """Assert method ``setUpClass`` creates correct class attributes.

        Verify that the method creates attributes named ``cfg`` and
        ``resources``.
        """
        for attr in {'cfg', 'resources'}:
            with self.subTest(attr=attr):
                self.assertTrue(hasattr(self.child, attr))

    def test_tear_down_class(self):
        """Call method ``tearDownClass``, and assert it deletes each resource.

        :meth:`pulp_smash.api.Client.delete` should be called once for each
        resource listed in ``resources``.
        """
        with mock.patch.object(api, 'Client') as client:
            self.child.tearDownClass()
        self.assertEqual(
            client.return_value.delete.call_count,
            len(self.child.resources),
        )
