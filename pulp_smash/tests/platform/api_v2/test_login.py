# coding=utf-8
"""Test the API's `authentication`_ functionality.

.. _authentication:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/authentication.html
"""
from __future__ import unicode_literals

from pulp_smash import api, selectors, utils
from pulp_smash.constants import ERROR_KEYS, LOGIN_KEYS, LOGIN_PATH


class LoginSuccessTestCase(utils.BaseAPITestCase):
    """Tests for successfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Successfully log in to the server."""
        super(LoginSuccessTestCase, cls).setUpClass()
        cls.response = api.Client(cls.cfg).post(LOGIN_PATH)

    def test_status_code(self):
        """Assert that the response has an HTTP 200 status code."""
        self.assertEqual(self.response.status_code, 200)

    def test_body(self):
        """Assert that the response is valid JSON and has correct keys."""
        self.assertEqual(frozenset(self.response.json().keys()), LOGIN_KEYS)


class LoginFailureTestCase(utils.BaseAPITestCase):
    """Tests for unsuccessfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Unsuccessfully log in to the server."""
        super(LoginFailureTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.echo_handler)
        cls.response = client.post(LOGIN_PATH, auth=('', ''))

    def test_status_code(self):
        """Assert that the response has an HTTP 401 status code."""
        self.assertEqual(self.response.status_code, 401)

    def test_body(self):
        """Assert that the response is valid JSON and has correct keys."""
        if selectors.bug_is_untestable(1412, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1412')
        self.assertEqual(frozenset(self.response.json().keys()), ERROR_KEYS)
