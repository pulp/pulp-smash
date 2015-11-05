# coding=utf-8
"""Test the API's `authentication`_ functionality.

.. _authentication:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/authentication.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from pulp_smash.constants import ERROR_KEYS, LOGIN_PATH
from unittest2 import TestCase

# Upon successfully logging in, the response should contain these keys.
_LOGIN_KEYS = {'certificate', 'key'}

# Failed login attempts produce a non-standard response.
#
# The ``href`` key is present prior to Pulp 3.0 for backward compatibility.
_LOGIN_ERROR_KEYS = ERROR_KEYS | {'href'}


class LoginSuccessTestCase(TestCase):
    """Tests for successfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Successfully log in to the server."""
        cfg = get_config()
        cls.response = requests.post(
            cfg.base_url + LOGIN_PATH,
            **cfg.get_requests_kwargs()
        )

    def test_status_code(self):
        """Assert that the response has an HTTP 200 status code."""
        self.assertEqual(self.response.status_code, 200)

    def test_body(self):
        """Assert that the response is valid JSON and has correct keys."""
        self.assertEqual(
            frozenset(self.response.json().keys()),
            _LOGIN_KEYS,
        )


class LoginFailureTestCase(TestCase):
    """Tests for unsuccessfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Unsuccessfully log in to the server."""
        cfg = get_config()
        cfg.auth = ('', '')
        cls.response = requests.post(
            cfg.base_url + LOGIN_PATH,
            **cfg.get_requests_kwargs()
        )

    def test_status_code(self):
        """Assert that the response has an HTTP 401 status code."""
        self.assertEqual(self.response.status_code, 401)

    def test_body(self):
        """Assert that the response is valid JSON and has correct keys."""
        self.assertEqual(
            frozenset(self.response.json().keys()),
            _LOGIN_ERROR_KEYS,
        )
