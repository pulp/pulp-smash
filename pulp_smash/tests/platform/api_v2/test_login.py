# coding=utf-8
"""Test the API's `authentication`_ functionality.

.. _authentication:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/authentication.html
"""
from __future__ import unicode_literals

import requests
from unittest2 import TestCase

from pulp_smash.config import get_config
from pulp_smash.constants import ERROR_KEYS, LOGIN_KEYS, LOGIN_PATH
from pulp_smash.utils import bug_is_untestable


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
        self.assertEqual(frozenset(self.response.json().keys()), LOGIN_KEYS)


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
        if bug_is_untestable(1412):
            self.skipTest('https://pulp.plan.io/issues/1412')
        self.assertEqual(frozenset(self.response.json().keys()), ERROR_KEYS)
