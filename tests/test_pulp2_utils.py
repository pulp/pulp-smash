# coding=utf-8
"""Unit tests for :mod:`pulp_smash.pulp2.utils`."""
import random
import unittest
from unittest import mock

from pulp_smash import api, cli, config, exceptions
from pulp_smash.pulp2.utils import (
    BaseAPITestCase,
    get_broker,
    pulp_admin_login,
    search_units,
    sync_repo,
    upload_import_erratum,
    upload_import_unit,
)


class BaseAPITestCaseTestCase(unittest.TestCase):
    """Test :class:`pulp_smash.pulp2.utils.BaseAPITestCase`."""

    @classmethod
    def setUpClass(cls):
        """Define a child class. Call setup and teardown methods on it.

        We define a child class in order to avoid altering
        :class:`pulp_smash.pulp2.utils.BaseAPITestCase`. Calling class methods
        on it would do so.
        """

        class Child(BaseAPITestCase):
            """An empty child class."""

            pass

        with mock.patch.object(config, "get_config"):
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
        for attr in {"cfg", "resources"}:
            with self.subTest(attr=attr):
                self.assertTrue(hasattr(self.child, attr))

    def test_tear_down_class(self):
        """Call method ``tearDownClass``, and assert it deletes each resource.

        :meth:`pulp_smash.api.Client.delete` should be called once for each
        resource listed in ``resources``, and once for
        :data:`pulp_smash.pulp2.constants.ORPHANS_PATH`.
        """
        with mock.patch.object(api, "Client") as client:
            self.child.tearDownClass()
        self.assertEqual(
            client.return_value.delete.call_count,
            len(self.child.resources) + 1,
        )


class GetBrokerTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.pulp2.utils.get_broker`."""

    def test_success(self):
        """Successfully generate a broker service management object.

        Assert that:

        * ``get_broker(…)`` returns a string.
        * The ``cfg`` argument is passed to the service object.
        * The "qpidd" broker is the preferred broker.
        """
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 0
            broker = get_broker(cfg=mock.Mock())
        self.assertEqual(broker, "qpidd")

    def test_failure(self):
        """Fail to generate a broker service management object.

        Assert that :class:`pulp_smash.exceptions.NoKnownBrokerError` is raised
        if the function cannot find a broker.
        """
        cfg = mock.Mock()
        cfg.get_base_url.return_value = "http://example.com"
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 1
            with self.assertRaises(exceptions.NoKnownBrokerError):
                get_broker(cfg)


class PulpAdminLoginTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.pulp2.utils.pulp_admin_login`."""

    def test_run(self):
        """Assert the function executes ``cli.Client.run``."""
        with mock.patch.object(cli, "Client") as client:
            cfg = config.PulpSmashConfig(
                pulp_auth=["admin", "admin"],
                pulp_version="1!0",
                pulp_selinux_enabled=True,
                hosts=[
                    config.PulpHost(
                        hostname="example.com", roles={"pulp cli": {}}
                    )
                ],
            )
            response = pulp_admin_login(cfg)
            self.assertIs(response, client.return_value.run.return_value)


class SearchUnitsTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.pulp2.utils.search_units`."""

    def test_defaults(self):
        """Verify that default parameters are correctly set."""
        with mock.patch.object(api, "Client") as client:
            search_units(mock.Mock(), {"_href": "foo/bar/"})
        self.assertEqual(client.call_args[0][1], api.json_handler)
        self.assertEqual(
            client.return_value.post.call_args[0][1], {"criteria": {}}
        )


class SyncRepoTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.pulp2.utils.sync_repo`."""

    def test_post(self):
        """Assert the function makes an HTTP POST request."""
        with mock.patch.object(api, "Client") as client:
            response = sync_repo(mock.Mock(), {"_href": "http://example.com"})
        self.assertIs(response, client.return_value.post.return_value)


class UploadImportErratumTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.pulp2.utils.upload_import_erratum`."""

    def test_post(self):
        """Assert the function makes an HTTP POST request."""
        with mock.patch.object(api, "Client") as client:
            # post() is called twice, first to start a content upload and
            # second to import and upload. In both cases, a dict is returned.
            # Our dict mocks the first case, and just happens to work in the
            # second case too.
            client.return_value.post.return_value = {
                "_href": "foo",
                "upload_id": "bar",
            }
            response = upload_import_erratum(
                mock.Mock(),  # cfg
                {"id": "abc123"},  # erratum
                {"_href": "http://example.com"},  # repo
            )
        self.assertIs(response, client.return_value.post.return_value)


class UploadImportUnitTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.pulp2.utils.upload_import_unit`."""

    def test_post(self):
        """Assert the function makes an HTTP POST request."""
        with mock.patch.object(api, "Client") as client:
            # post() is called twice, first to start a content upload and
            # second to import and upload. In both cases, a dict is returned.
            # Our dict mocks the first case, and just happens to work in the
            # second case too.
            client.return_value.post.return_value = {
                "_href": "foo",
                "upload_id": "bar",
            }
            response = upload_import_unit(
                mock.Mock(),  # cfg
                b"my unit",  # unit
                {},  # import_params
                {"_href": "http://example.com"},  # repo
            )
        self.assertIs(response, client.return_value.post.return_value)
