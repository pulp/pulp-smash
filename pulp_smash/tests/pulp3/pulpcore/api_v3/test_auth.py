# coding=utf-8
"""Tests for Pulp 3's authentication API.

For more information, see the documentation on `Authentication
<http://docs.pulpproject.org/en/3.0/nightly/integration_guide/rest_api/authentication.html>`_.
"""
import unittest
from random import choice
from time import sleep
from urllib.parse import urljoin

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from pulp_smash import api, config, utils
from pulp_smash.tests.pulp3.constants import BASE_PATH, JWT_PATH, USER_PATH
from pulp_smash.tests.pulp3.utils import JWTAuth
from pulp_smash.tests.pulp3.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class AuthTestCase(unittest.TestCase):
    """Test Pulp3 Authentication."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()

    def test_base_auth_success(self):
        """Perform HTTP basic authentication with valid credentials.

        Assert that a response indicating success is returned.
        """
        api.Client(self.cfg, api.json_handler).get(
            BASE_PATH,
            auth=HTTPBasicAuth(self.cfg.pulp_auth[0], self.cfg.pulp_auth[1]),
        )

    def test_base_auth_failure(self):
        """Perform HTTP basic authentication with invalid credentials.

        Assert that a response indicating failure is returned.
        """
        with self.assertRaises(HTTPError):
            api.Client(self.cfg, api.json_handler).get(
                BASE_PATH,
                auth=HTTPBasicAuth(self.cfg.pulp_auth[0], utils.uuid4()),
            )

    def test_jwt_success(self):
        """Perform JWT authentication with valid credentials.

        Assert that a response indicating success is returned.
        """
        client = api.Client(self.cfg, api.json_handler)
        token = client.post(JWT_PATH, {
            'username': self.cfg.pulp_auth[0],
            'password': self.cfg.pulp_auth[1],
        })
        client.get(BASE_PATH, auth=JWTAuth(token['token']))

    def test_jwt_failure(self):
        """Perform JWT authentication with invalid credentials.

        Assert that a response indicating failure is returned.
        """
        with self.assertRaises(HTTPError):
            api.Client(self.cfg, api.json_handler).post(
                JWT_PATH,
                {'username': self.cfg.pulp_auth[0], 'password': utils.uuid4()},
            )


class JWTResetTestCase(unittest.TestCase):
    """Perform series of tests related to JWT reset."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_reset_jwt(self):
        """Perform JWT reset.

        Do the following:

        1. Generate 2 tokens using ``JWT`` as authentication method.
        2. Use ``token_1`` to reset the ``JWT`` secret key which is used to
           sign both **tokens**.
        3. Attempt to use the ``token_2`` to access any endpoint that requires
           credential.
        4. Assert that a response indicating failure is returned.
        """
        token_1 = self.client.post(JWT_PATH, {
            'username': self.cfg.pulp_auth[0],
            'password': self.cfg.pulp_auth[1]
        })

        token_2 = self.client.post(JWT_PATH, {
            'username': self.cfg.pulp_auth[0],
            'password': self.cfg.pulp_auth[1]
        })

        self.client.post(urljoin(USER_PATH,
                                 urljoin((self.cfg.pulp_auth[0] + '/'),
                                         'jwt_reset/')),
                         auth=JWTAuth(token_1['token']))

        with self.assertRaises(HTTPError):
            self.client.get(BASE_PATH, auth=JWTAuth(token_2['token']))

    def test_reset_jwt_basic_auth(self):
        """Using ``BasichAuth`` to reset ``JWT`` secret key.

        Assert that no failure is returned.
        """
        self.client.post(urljoin(USER_PATH,
                                 urljoin(
                                     (self.cfg.pulp_auth[0] + '/'),
                                     'jwt_reset/'
                                 )),
                         auth=HTTPBasicAuth(self.cfg.pulp_auth[0],
                                            self.cfg.pulp_auth[1]))

        self.client.get(BASE_PATH)

    def test_reset_user_tokens(self):
        """Test whether when deleting a user all user`s JWT are invalidated.

        Do the following:

        1. Create a user, and obtain a ``JWT`` token.
        2. Delete the previous created user.
        3. Verify whether the user`s token still valid.
        """
        attrs = {
            'username': utils.uuid4(),
            'password': utils.uuid4(),
            'is_superuser': choice((True, False)),
        }

        self.client.response_handler = api.echo_handler
        user = self.client.post(USER_PATH, attrs).json()
        token = self.client.post(JWT_PATH, {
            'username': attrs['username'],
            'password': attrs['password']
        }).json()

        self.client.get(BASE_PATH, auth=JWTAuth(token['token']))
        self.client.delete(user['_href'])
        sleep(5)

        with self.assertRaises(HTTPError):
            response = self.client.get(BASE_PATH, auth=JWTAuth(token['token']))
            response.raise_for_status()
