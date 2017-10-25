# coding=utf-8
"""Tests that CRUD users."""
from random import choice
from time import sleep
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import USER_PATH
from pulp_smash.tests.pulp3.utils import get_auth


class UsersCRUDTestCase(unittest.TestCase):
    """CRUD users."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.password = utils.uuid4()
        cls.username = utils.uuid4()
        cls.user = {}

    def setUp(self):
        """Create an API client."""
        self.client = api.Client(self.cfg, api.code_handler)
        self.client.request_kwargs['auth'] = get_auth()

    def test_01_create_user(self):
        """Create user."""
        type(self).user = self.client.post(USER_PATH, {
            'username': self.username,
            'password': self.password,
            'is_superuser': choice([True, False])
        }).json()

    @selectors.skip_if(bool, 'user', False)
    def test_02_read_user(self):
        """Read a user by its href.

        Assert that response contains the correct user.
        """
        user = self.client.get(self.user['_href']).json()
        self.assertEqual(self.user['username'], user['username'])

    @selectors.skip_if(bool, 'user', False)
    def test_03_fully_update_user(self):
        """Update a user info using HTTP PUT."""
        if selectors.bug_is_untestable(3125, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3125')
        user = self.client.get(self.user['_href']).json()
        data = utils.uuid4()
        user['username'] = data
        user['password'] = data
        self.client.put(user['_href'], user)
        sleep(5)

        # verify update
        user = self.client.get(user['_href']).json()
        self.assertEqual(data, user['username'])

    @selectors.skip_if(bool, 'user', False)
    def test_03_partially_update_user(self):
        """Update a user info using HTTP PATCH."""
        user = self.client.get(self.user['_href']).json()
        is_superuser = user['is_superuser']
        user['is_superuser'] = self.invert_super_user(user['is_superuser'])
        self.client.patch(user['_href'], user)
        sleep(5)

        # verify update
        user = self.client.get(user['_href']).json()
        self.assertNotEqual(is_superuser, user['is_superuser'])

    @selectors.skip_if(bool, 'user', False)
    def test_04_delete_user(self):
        """Delete an user."""
        self.client.delete(self.user['_href'])
        sleep(5)

        # verify delete
        with self.assertRaises(HTTPError):
            self.client.get(self.user['_href'])

    @staticmethod
    def invert_super_user(is_superuser):
        """Return an inverted status for ``is_superuser``."""
        if is_superuser is True:
            return False
        return True
