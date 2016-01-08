# coding=utf-8
"""Test the API's `content applicability` functionality.

.. _content applicability:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/consumer/applicability.html
"""
from __future__ import unicode_literals

from packaging.version import Version
from unittest2 import TestCase

from pulp_smash import api, config, selectors
from pulp_smash.constants import CALL_REPORT_KEYS

_PATHS = {
    'consumer': '/pulp/api/v2/consumers/actions/content/regenerate_applicability/',  # noqa
    'repo': '/pulp/api/v2/repositories/actions/content/regenerate_applicability/',  # noqa
}


class SuccessTestCase(TestCase):
    """Generate content applicability for updated consumers and repos."""

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        cls.cfg = config.get_config()
        client = api.Client(cls.cfg, api.echo_handler)
        cls.responses = {
            key: client.post(path, {key + '_criteria': {}})
            for key, path in _PATHS.items()
        }

    def test_status_code(self):
        """Assert each response has an HTTP 202 status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 202)

    def test_body(self):
        """Assert each response is JSON and appears to be a call report."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                if (key == 'repo' and self.cfg.version >= Version('2.8') and
                        selectors.bug_is_untestable(1448)):
                    self.skipTest('https://pulp.plan.io/issues/1448')
                response_keys = frozenset(response.json().keys())
                self.assertEqual(response_keys, CALL_REPORT_KEYS)


class FailureTestCase(TestCase):
    """Fail to generate content applicability for consumers and repos."""

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        client = api.Client(config.get_config(), api.echo_handler)
        cls.responses = {
            key: client.post(path, {key + '_criteriaa': {}})
            for key, path in _PATHS.items()
        }

    def test_status_code(self):
        """Assert each response has an HTTP 400 status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 400)

    def test_body(self):
        """Assert each response is JSON and doesn't look like a call report."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                response_keys = frozenset(response.json().keys())
                self.assertNotEqual(response_keys, CALL_REPORT_KEYS)
