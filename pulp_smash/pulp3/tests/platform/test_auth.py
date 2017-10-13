# coding=utf-8
"""Tests for Pulp3 authentication API."""
import unittest

from packaging.version import Version
from requests.auth import HTTPBasicAuth

from pulp_smash import api, config
from pulp_smash.pulp3.constants import USER_PATH, JWT_PATH
from pulp_smash.pulp3.utils import adjust_url, get_base_url, get_url, JWTAuth


class AuthTestCase(unittest.TestCase):
    """Test Pulp3 Authentication."""

    def setUp(self):
        """Create config variable."""
        self.cfg = config.get_config()
        if self.cfg.version < Version('3.0'):
            self.skipTest('Requires Pulp 3.0 or higher')
        self.url = adjust_url(get_url(get_base_url(), USER_PATH))

    def test_auth(self):
        """Test Pulp3 Basic Authentication."""
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        client.get(USER_PATH, auth=HTTPBasicAuth(
            self.cfg.pulp_auth[0], self.cfg.pulp_auth[1]
        ))

    def test_jwt(self):
        """Test Pulp3 JWT Authentication."""
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        token = client.post(JWT_PATH, {
            'username': self.cfg.pulp_auth[0],
            'password': self.cfg.pulp_auth[1],
        })
        client.get(USER_PATH, auth=JWTAuth(token['token'], 'JWT'))
