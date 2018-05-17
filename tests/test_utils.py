# coding=utf-8
"""Unit tests for :mod:`pulp_smash.utils`."""
import random
import unittest
from unittest import mock


from pulp_smash import api, cli, config, exceptions, utils


class UUID4TestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.uuid4`."""

    def test_type(self):
        """Assert the method returns a unicode string."""
        self.assertIsInstance(utils.uuid4(), str)


class GetBrokerTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.get_broker`."""

    def test_success(self):
        """Successfully generate a broker service management object.

        Assert that:

        * ``get_broker(…)`` returns a string.
        * The ``cfg`` argument is passed to the service object.
        * The "qpidd" broker is the preferred broker.
        """
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 0
            broker = utils.get_broker(cfg=mock.Mock())
        self.assertEqual(broker, 'qpidd')

    def test_failure(self):
        """Fail to generate a broker service management object.

        Assert that :class:`pulp_smash.exceptions.NoKnownBrokerError` is raised
        if the function cannot find a broker.
        """
        cfg = mock.Mock()
        cfg.get_base_url.return_value = 'http://example.com'
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 1
            with self.assertRaises(exceptions.NoKnownBrokerError):
                utils.get_broker(cfg)


class BaseAPITestCase(unittest.TestCase):
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
        :data:`pulp_smash.pulp2.constants.ORPHANS_PATH`.
        """
        with mock.patch.object(api, 'Client') as client:
            self.child.tearDownClass()
        self.assertEqual(
            client.return_value.delete.call_count,
            len(self.child.resources) + 1,
        )


class IsRootTestCase(unittest.TestCase):
    """Test ``pulp_smash.utils.is_root``."""

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


class SyncRepoTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.sync_repo`."""

    def test_post(self):
        """Assert the function makes an HTTP POST request."""
        with mock.patch.object(api, 'Client') as client:
            response = utils.sync_repo(
                mock.Mock(),
                {'_href': 'http://example.com'},
            )
        self.assertIs(response, client.return_value.post.return_value)


class UploadImportUnitTestCase(unittest.TestCase):
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
                mock.Mock(),  # cfg
                b'my unit',  # unit
                {},  # import_params
                {'_href': 'http://example.com'},  # repo
            )
        self.assertIs(response, client.return_value.post.return_value)


class UploadImportErratumTestCase(unittest.TestCase):
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
            response = utils.upload_import_erratum(
                mock.Mock(),  # cfg
                {'id': 'abc123'},  # erratum
                'http://example.com',  # repo_href
            )
        self.assertIs(response, client.return_value.post.return_value)


class PulpAdminLoginTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.pulp_admin_login`."""

    def test_run(self):
        """Assert the function executes ``cli.Client.run``."""
        with mock.patch.object(cli, 'Client') as client:
            cfg = config.PulpSmashConfig(
                pulp_auth=['admin', 'admin'],
                pulp_version='1!0',
                pulp_selinux_enabled=True,
                hosts=[
                    config.PulpHost(
                        hostname='example.com',
                        roles={'pulp cli': {}},
                    )
                ]
            )
            response = utils.pulp_admin_login(cfg)
            self.assertIs(response, client.return_value.run.return_value)


class GetSha256ChecksumTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.get_sha256_checksum`."""

    def test_all(self):
        """Call the function three times, with two URLs.

        Call the function with the first URL, the second URL and the first URL
        again. Verify that:

        * No download is attempted during the third call.
        * The first and second calls return different checksums.
        * The first and third calls return identical checksums.
        """
        urls_blobs = (
            ('http://example.com', b'abc'),
            ('http://example.org', b'123'),
            ('HTTP://example.com', b'abc'),
        )
        checksums = []
        with mock.patch.object(utils, 'http_get') as http_get:
            for url, blob in urls_blobs:
                http_get.return_value = blob
                checksums.append(utils.get_sha256_checksum(url))
        self.assertEqual(http_get.call_count, 2)
        self.assertNotEqual(checksums[0], checksums[1])
        self.assertEqual(checksums[0], checksums[2])


class SearchUnitsTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.search_units`."""

    def test_defaults(self):
        """Verify that default parameters are correctly set."""
        with mock.patch.object(api, 'Client') as client:
            utils.search_units(mock.Mock(), {'_href': 'foo/bar/'})
        self.assertEqual(client.call_args[0][1], api.json_handler)
        self.assertEqual(
            client.return_value.post.call_args[0][1],
            {'criteria': {}},
        )


class OsIsF26TestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.os_is_f26`."""

    def test_returncode_zero(self):
        """Assert true is returned if the CLI command returns zero."""
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 0
            response = utils.os_is_f26(mock.Mock())
        self.assertTrue(response)

    def test_returncode_nonzero(self):
        """Assert false is returned if the CLI command returns non-zero."""
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.returncode = 1
            response = utils.os_is_f26(mock.Mock())
        self.assertFalse(response)
