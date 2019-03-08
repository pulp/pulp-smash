# coding=utf-8
"""Unit tests for :mod:`pulp_smash.api`."""
import unittest
from unittest import mock

from packaging.version import Version

from pulp_smash import api, config


_HANDLER_ARGS = ("client", "response")


class EchoHandlerTestCase(unittest.TestCase):
    """Tests for :func:`pulp_smash.api.echo_handler`."""

    def test_return(self):
        """Assert the passed-in ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        self.assertIs(kwargs["response"], api.echo_handler(**kwargs))

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is not called."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        api.echo_handler(**kwargs)
        self.assertEqual(kwargs["response"].raise_for_status.call_count, 0)

    def test_202_check_skipped(self):
        """Assert HTTP 202 responses are not treated specially."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        with mock.patch.object(api, "_handle_202") as handle_202:
            api.echo_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 0)


class CodeHandlerTestCase(unittest.TestCase):
    """Tests for :func:`pulp_smash.api.code_handler`."""

    def test_return(self):
        """Assert the passed-in ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        self.assertIs(kwargs["response"], api.code_handler(**kwargs))

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is called."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        api.code_handler(**kwargs)
        self.assertEqual(kwargs["response"].raise_for_status.call_count, 1)

    def test_202_check_skipped(self):
        """Assert HTTP 202 responses are not treated specially."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        with mock.patch.object(api, "_handle_202") as handle_202:
            api.code_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 0)


class SafeHandlerTestCase(unittest.TestCase):
    """Tests for :func:`pulp_smash.api.safe_handler`."""

    def test_return(self):
        """Assert the passed-in ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        self.assertIs(kwargs["response"], api.safe_handler(**kwargs))

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is called."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        api.safe_handler(**kwargs)
        self.assertEqual(kwargs["response"].raise_for_status.call_count, 1)

    def test_202_check_run(self):
        """Assert HTTP 202 responses are treated specially."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        with mock.patch.object(api, "_handle_202") as handle_202:
            api.safe_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 1)


class JsonHandlerTestCase(unittest.TestCase):
    """Tests for :func:`pulp_smash.api.json_handler`."""

    def test_return(self):
        """Assert the JSON-decoded body of ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        out = api.json_handler(**kwargs)
        self.assertEqual(kwargs["response"].json.return_value, out)

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is called."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        api.json_handler(**kwargs)
        self.assertEqual(kwargs["response"].raise_for_status.call_count, 1)

    def test_202_check_run(self):
        """Assert HTTP 202 responses are treated specially."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        with mock.patch.object(api, "_handle_202") as handle_202:
            api.json_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 1)

    def test_204_check_run(self):
        """Assert HTTP 204 responses are treated specially."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        kwargs["response"].status_code = 204
        with mock.patch.object(api, "_handle_202"):
            api.json_handler(**kwargs)
        self.assertEqual(kwargs["response"].json.call_count, 0)


class PageHandlerTestCase(unittest.TestCase):
    """Tests for :func:`pulp_smash.api.page_handler`."""

    def test_pulp_2_error(self):
        """Assert this handler can't be used with Pulp 2."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        kwargs["client"]._cfg.pulp_version = Version(
            "2"
        )  # pylint:disable=protected-access
        with self.assertRaises(ValueError):
            api.page_handler(**kwargs)

    def test_204_check_run(self):
        """Assert HTTP 204 responses are immediately returned."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        kwargs["client"]._cfg.pulp_version = Version(
            "3"
        )  # pylint:disable=protected-access
        with mock.patch.object(api, "json_handler") as json_handler:
            json_handler.return_value = mock.Mock()
            return_value = api.page_handler(**kwargs)
        self.assertIs(return_value, json_handler.return_value)

    def test_not_a_page(self):
        """Assert non-paginated responses are immediately returned."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        kwargs["client"]._cfg.pulp_version = Version(
            "3"
        )  # pylint:disable=protected-access
        with mock.patch.object(api, "json_handler") as json_handler:
            json_handler.return_value = {}
            return_value = api.page_handler(**kwargs)
        self.assertIs(return_value, json_handler.return_value)

    def test_is_a_page(self):
        """Assert paginated responses are collected."""
        kwargs = {key: mock.Mock() for key in _HANDLER_ARGS}
        kwargs["client"]._cfg.pulp_version = Version(
            "3"
        )  # pylint:disable=protected-access
        with mock.patch.object(api, "json_handler") as json_handler:
            json_handler.return_value = {"results": None}
            with mock.patch.object(api, "_walk_pages") as walk_pages:
                walk_pages.return_value = ((1, 2), (3, 4))
                return_value = api.page_handler(**kwargs)
        self.assertEqual(return_value, [1, 2, 3, 4])


class ClientTestCase(unittest.TestCase):
    """Tests for :class:`pulp_smash.api.Client`."""

    @classmethod
    def setUpClass(cls):
        """Assert methods delegate to :meth:`pulp_smash.api.Client.request`.

        All methods on :class:`pulp_smash.api.Client`, such as
        :meth:`pulp_smash.api.Client.delete`, should delegate to
        :meth:`pulp_smash.api.Client.request`. Mock out ``request`` and call
        the other methods.
        """
        methods = {"delete", "get", "head", "options", "patch", "post", "put"}
        cls.mocks = {}
        for method in methods:
            client = api.Client(_get_pulp_smash_config())
            with mock.patch.object(client, "request") as request:
                getattr(client, method)("")
            cls.mocks[method] = request

    def test_called_once(self):
        """Assert each method calls ``request`` exactly once."""
        for meth, request in self.mocks.items():
            with self.subTest(meth=meth):
                self.assertEqual(request.call_count, 1)

    def test_http_action(self):
        """Assert each method calls ``request`` with the right HTTP action."""
        for meth, request in self.mocks.items():
            with self.subTest(meth=meth):
                self.assertEqual(request.call_args[0][0], meth.upper())


class ClientTestCase2(unittest.TestCase):
    """More tests for :class:`pulp_smash.api.Client`."""

    def test_response_handler(self):
        """Assert ``__init__`` saves the ``response_handler`` argument.

        The argument should be saved as an instance attribute.
        """
        response_handler = mock.Mock()
        client = api.Client(_get_pulp_smash_config(), response_handler)
        self.assertIs(client.response_handler, response_handler)

    def test_json_arg(self):
        """Assert methods with a ``json`` argument pass on that argument."""
        json = mock.Mock()
        client = api.Client(_get_pulp_smash_config())
        for method in {"patch", "post", "put"}:
            with self.subTest(method=method):
                with mock.patch.object(client, "request") as request:
                    getattr(client, method)("some url", json)
                self.assertEqual(
                    request.call_args[0], (method.upper(), "some url")
                )
                self.assertIs(request.call_args[1]["json"], json)


def _get_pulp_smash_config():
    """Return a config object with made-up attributes.

    :rtype: pulp_smash.config.PulpSmashConfig
    """
    return config.PulpSmashConfig(
        pulp_auth=["admin", "admin"],
        pulp_version="1!0",
        pulp_selinux_enabled=True,
        hosts=[
            config.PulpHost(
                hostname="example.com", roles={"api": {"scheme": "http"}}
            )
        ],
    )
