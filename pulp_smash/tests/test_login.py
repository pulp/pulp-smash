# coding=utf-8
"""Test the API's `authentication`_ functionality.

.. _authentication:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/authentication.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from unittest2 import TestCase


LOGIN_KEYS = {'certificate', 'key'}
LOGIN_PATH = '/pulp/api/v2/actions/login/'


class LoginSuccessTestCase(TestCase):
    """Tests for successfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Successfully log in to the server."""
        config = get_config()
        base_url = config.pop('base_url')
        cls.response = requests.post(base_url + LOGIN_PATH, **config)

    def test_status_code(self):
        """Assert that the response has an HTTP 200 status code."""
        self.assertEqual(self.response.status_code, 200)

    def test_body(self):
        """Assert that the response is valid JSON and has "key" and
        "certificate" keys.

        """
        self.assertEqual(set(self.response.json().keys()), LOGIN_KEYS)


class LoginFailureTestCase(TestCase):
    """Tests for unsuccessfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Unsuccessfully log in to the server."""
        config = get_config()
        base_url = config.pop('base_url')
        config['auth'] = ('', '')
        cls.response = requests.post(base_url + LOGIN_PATH, **config)

    def test_status_code(self):
        """Assert that the response has an HTTP 401 status code."""
        self.assertEqual(self.response.status_code, 401)

    def test_body(self):
        """Assert that the response is valid JSON and does not have "key" and
        "certificate" keys.

        """
        self.assertNotEqual(set(self.response.json().keys()), LOGIN_KEYS)
