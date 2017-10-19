# coding=utf-8
"""Tests for Pulp 3's authentication API.

For more information, see the documentation on `Authentication
<http://docs.pulpproject.org/en/3.0/nightly/integration_guide/rest_api/authentication.html>`_.
"""
import unittest

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from pulp_smash import api, config, utils
from pulp_smash.tests.pulp3.constants import BASE_PATH, JWT_PATH
from pulp_smash.tests.pulp3.utils import adjust_url, get_base_url, JWTAuth
from pulp_smash.tests.pulp3.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class AuthTestCase(unittest.TestCase):
    """Test Pulp3 Authentication."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.url = adjust_url(get_base_url())

    def test_base_auth_success(self):
        """Perform HTTP basic authentication with valid credentials.

        Assert that a response indicating success is returned.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        client.get(BASE_PATH, auth=HTTPBasicAuth(
            self.cfg.pulp_auth[0],
            self.cfg.pulp_auth[1],
        ))

    def test_base_auth_failure(self):
        """Perform HTTP basic authentication with invalid credentials.

        Assert that a response indicating failure is returned.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        with self.assertRaises(HTTPError):
            client.get(BASE_PATH, auth=HTTPBasicAuth(
                self.cfg.pulp_auth[0],
                utils.uuid4(),
            ))

    def test_jwt_success(self):
        """Perform JWT authentication with valid credentials.

        Assert that a response indicating success is returned.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        token = client.post(JWT_PATH, {
            'username': self.cfg.pulp_auth[0],
            'password': self.cfg.pulp_auth[1],
        })
        client.get(BASE_PATH, auth=JWTAuth(token['token'], 'JWT'))

    def test_jwt_failure(self):
        """Perform JWT authentication with invalid credentials.

        Assert that a response indicating failure is returned.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        with self.assertRaises(HTTPError):
            client.post(JWT_PATH, {
                'username': self.cfg.pulp_auth[0],
                'password': utils.uuid4(),
            })
