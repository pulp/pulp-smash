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
        resource listed in ``resources``, and once for
        :data:`pulp_smash.constants.ORPHANS_PATH`.
        """
        with mock.patch.object(api, 'Client') as client:
            self.child.tearDownClass()
        self.assertEqual(
            client.return_value.delete.call_count,
            len(self.child.resources) + 1,
        )


class IsRootTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.is_root`."""

    def test_true(self):
        """Assert the method returns ``True`` when root."""
        with mock.patch.object(cli, 'Client') as clien:
            clien.return_value.run.return_value.stdout.strip.return_value = '0'
            self.assertTrue(utils.is_root(None))

    def test_false(self):
        """Assert the method returns ``False`` when non-root."""
        with mock.patch.object(cli, 'Client') as clien:
            clien.return_value.run.return_value.stdout.strip.return_value = '1'
            self.assertFalse(utils.is_root(None))


class SkipIfTypeIsUnsupportedTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.skip_if_type_is_unsupported`."""

    def setUp(self):
        """Generate a random unit type ID."""
        self.unit_type_id = utils.uuid4()

    def test_type_is_supported(self):
        """Assert nothing happens if the given unit type is supported.

        Also assert :func:`pulp_smash.config.get_config` is not called, as we
        provide a :class:`pulp_smash.config.ServerConfig` argument.
        """
        with mock.patch.object(config, 'get_config') as get_config:
            with mock.patch.object(utils, 'get_unit_type_ids') as get_u_t_ids:
                get_u_t_ids.return_value = {self.unit_type_id}
                self.assertIsNone(utils.skip_if_type_is_unsupported(
                    self.unit_type_id,
                    mock.Mock(),  # a ServerConfig object
                ))
        self.assertEqual(get_config.call_count, 0)

    def test_type_is_unsupported(self):
        """Assert ``SkipTest`` is raised if the given unit type is unsupported.

        Also assert :func:`pulp_smash.config.get_config` is called, as we do
        not provide a :class:`pulp_smash.config.ServerConfig` argument.
        """
        with mock.patch.object(config, 'get_config') as get_config:
            with mock.patch.object(utils, 'get_unit_type_ids') as get_u_t_ids:
                get_u_t_ids.return_value = set()
                with self.assertRaises(unittest2.SkipTest):
                    utils.skip_if_type_is_unsupported(self.unit_type_id)
        self.assertEqual(get_config.call_count, 1)


class GetUnitTypeIdsTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.skip_if_type_is_unsupported`."""

    def test_ids_are_returned(self):
        """Assert each unit type ID in the server response is returned."""
        unit_type_ids = {random.randrange(999) for _ in range(10)}
        # The server hands back a list of dicts, where each dict contains
        # information about a single unit type.
        unit_types = [{'id': unit_type_id} for unit_type_id in unit_type_ids]
        with mock.patch.object(api, 'Client') as client:
            client.return_value.get.return_value.json.return_value = unit_types
            self.assertEqual(
                utils.get_unit_type_ids(mock.Mock()),
                unit_type_ids,
            )


class SyncRepoTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.sync_repo`."""

    def test_post(self):
        """Assert the function makes an HTTP POST request."""
        with mock.patch.object(api, 'Client') as client:
            response = utils.sync_repo(mock.Mock(), 'http://example.com')
        self.assertIs(response, client.return_value.post.return_value)


class UploadImportUnitTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.upload_import_unit`."""

    def test_post(self):
        """Assert the function makes an HTTP POST request."""
        with mock.patch.object(api, 'Client') as client:
            # post() is called twice, first to start a content upload and
            # second to import and upload. In both cases, a dict is returned.
            # Our dict mocks the first case, and just happens to work in the
            # second case too.
            client.return_value.post.return_value = {
                '_href': 'foo',
                'upload_id': 'bar',
            }
            response = utils.upload_import_unit(
                mock.Mock(),  # server_config
                b'my unit',
                'my unit type id',
                'http://example.com',  # repo_href
            )
        self.assertIs(response, client.return_value.post.return_value)


class PulpAdminLoginTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.utils.pulp_admin_login`."""

    def test_run(self):
        """Assert the function executes ``cli.Client.run``."""
        with mock.patch.object(cli, 'Client') as client:
            cfg = config.ServerConfig('http://example.com', auth=['u', 'p'])
            response = utils.pulp_admin_login(cfg)
            self.assertIs(response, client.return_value.run.return_value)
