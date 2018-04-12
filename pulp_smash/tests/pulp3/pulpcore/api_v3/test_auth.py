# coding=utf-8
"""Tests for Pulp 3's authentication API.

For more information, see the documentation on `Authentication
<http://docs.pulpproject.org/en/3.0/nightly/integration_guide/rest_api/authentication.html>`_.
"""
import unittest
from urllib.parse import urljoin

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import BASE_PATH, JWT_PATH, USER_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_smash.tests.pulp3.utils import JWTAuth


class AuthTestCase(unittest.TestCase, utils.SmokeTest):
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
        if selectors.bug_is_untestable(3248, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3248')
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
        if selectors.bug_is_untestable(3248, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3248')
        with self.assertRaises(HTTPError):
            api.Client(self.cfg, api.json_handler).post(
                JWT_PATH,
                {'username': self.cfg.pulp_auth[0], 'password': utils.uuid4()},
            )


class JWTResetTestCase(unittest.TestCase):
    """Perform series of tests related to JWT reset."""

    def setUp(self):
        """Create a user and several JWT tokens for that user.

        Also, verify that the tokens are valid.
        """
        # Create a user.
        self.cfg = config.get_config()
        if selectors.bug_is_untestable(3248, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3248')
        auth = {'username': utils.uuid4(), 'password': utils.uuid4()}
        client = api.Client(self.cfg, api.json_handler)
        self.user = client.post(USER_PATH, auth)
        self.addCleanup(client.delete, self.user['_href'])

        # Create tokens for that user, and verify they're valid.
        self.tokens = tuple((
            client.post(JWT_PATH, auth) for _ in range(2)
        ))
        for token in self.tokens:
            client.get(BASE_PATH, auth=JWTAuth(token['token']))

    def test_reset_tokens(self):
        """Repeatedly reset the user's tokens, and verify they're invalid.

        Repeatedly resetting tokens ensures that token resets work even when a
        user has no tokens.
        """
        path = urljoin(USER_PATH, self.user['username'] + '/')
        path = urljoin(path, 'jwt_reset/')
        client = api.Client(self.cfg)
        for _ in range(10):
            client.post(path)
        for token in self.tokens:
            with self.assertRaises(HTTPError):
                client.get(BASE_PATH, auth=JWTAuth(token['token']))

    def test_delete_user(self):
        """Delete the user, and verify their tokens are invalid."""
        self.doCleanups()
        client = api.Client(self.cfg)
        for token in self.tokens:
            with self.assertRaises(HTTPError):
                client.get(BASE_PATH, auth=JWTAuth(token['token']))
