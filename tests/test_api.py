# coding=utf-8
"""Unit tests for :mod:`pulp_smash.api`."""
from __future__ import unicode_literals

import mock
import unittest2

from pulp_smash import api, config


class EchoHandlerTestCase(unittest2.TestCase):
    """Tests for :func:`pulp_smash.api.echo_handler`."""

    def test_return(self):
        """Assert the passed-in ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        self.assertIs(kwargs['response'], api.echo_handler(**kwargs))

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is not called."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        api.echo_handler(**kwargs)
        self.assertEqual(kwargs['response'].raise_for_status.call_count, 0)

    def test_202_check_skipped(self):
        """Assert HTTP 202 responses are not treated specially."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        with mock.patch.object(api, '_handle_202') as handle_202:
            api.echo_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 0)


class SafeHandlerTestCase(unittest2.TestCase):
    """Tests for :func:`pulp_smash.api.safe_handler`."""

    def test_return(self):
        """Assert the passed-in ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        self.assertIs(kwargs['response'], api.safe_handler(**kwargs))

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is called."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        api.safe_handler(**kwargs)
        self.assertEqual(kwargs['response'].raise_for_status.call_count, 1)

    def test_202_check_run(self):
        """Assert HTTP 202 responses are not treated specially."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        with mock.patch.object(api, '_handle_202') as handle_202:
            api.safe_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 1)


class JsonHandlerTestCase(unittest2.TestCase):
    """Tests for :func:`pulp_smash.api.json_handler`."""

    def test_return(self):
        """Assert the JSON-decoded body of ``response`` is returned."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        out = api.json_handler(**kwargs)
        self.assertEqual(kwargs['response'].json.return_value, out)

    def test_raise_for_status(self):
        """Assert ``response.raise_for_status()`` is called."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        api.json_handler(**kwargs)
        self.assertEqual(kwargs['response'].raise_for_status.call_count, 1)

    def test_202_check_run(self):
        """Assert HTTP 202 responses are not treated specially."""
        kwargs = {key: mock.Mock() for key in ('server_config', 'response')}
        with mock.patch.object(api, '_handle_202') as handle_202:
            api.json_handler(**kwargs)
        self.assertEqual(handle_202.call_count, 1)


class ClientTestCase(unittest2.TestCase):
    """Tests for :class:`pulp_smash.api.Client`."""

    @classmethod
    def setUpClass(cls):
        """Assert methods delegate to :meth:`pulp_smash.api.Client.request`.

        All methods on :class:`pulp_smash.api.Client`, such as
        :meth:`pulp_smash.api.Client.delete`, should delegate to
        :meth:`pulp_smash.api.Client.request`. Mock out ``request`` and call
        the other methods.
        """
        methods = {'delete', 'get', 'head', 'options', 'patch', 'post', 'put'}
        cls.mocks = {}
        for method in methods:
            client = api.Client(config.ServerConfig('http://example.com'))
            with mock.patch.object(client, 'request') as request:
                getattr(client, method)('')
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


class ClientTestCase2(unittest2.TestCase):
    """More tests for :class:`pulp_smash.api.Client`."""

    def test_response_handler(self):
        """Assert ``__init__`` saves the ``response_handler`` argument.

        The argument should be saved as an instance attribute.
        """
        response_handler = mock.Mock()
        client = api.Client(config.ServerConfig('base url'), response_handler)
        self.assertIs(client.response_handler, response_handler)

    def test_json_arg(self):
        """Assert methods with a ``json`` argument pass on that argument."""
        json = mock.Mock()
        client = api.Client(config.ServerConfig('base url'))
        for method in {'patch', 'post', 'put'}:
            with self.subTest(method=method):
                with mock.patch.object(client, 'request') as request:
                    getattr(client, method)('some url', json)
                self.assertIs(request.call_args[1]['json'], json)
