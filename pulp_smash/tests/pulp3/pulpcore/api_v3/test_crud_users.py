# coding=utf-8
"""Tests that CRUD users."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.pulp3.constants import USER_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_smash.pulp3.utils import get_auth


class UsersCRUDTestCase(unittest.TestCase):
    """CRUD users."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.user = {}

    def setUp(self):
        """Create an API client."""
        self.client = api.Client(self.cfg, api.json_handler)
        self.client.request_kwargs['auth'] = get_auth()

    def test_01_create_user(self):
        """Create a user."""
        attrs = _gen_verbose_user_attrs()
        type(self).user = self.client.post(USER_PATH, attrs)
        for key, val in attrs.items():
            with self.subTest(key=key):
                if key == 'password':
                    self.assertNotIn(key, self.user)
                else:
                    self.assertEqual(self.user[key], val)

    @selectors.skip_if(bool, 'user', False)
    def test_02_read_user(self):
        """Read a user byt its _href."""
        user = self.client.get(self.user['_href'])
        for key, val in user.items():
            with self.subTest(key=key):
                self.assertEqual(val, self.user[key])

    @selectors.skip_if(bool, 'user', False)
    def test_02_read_username(self):
        """Read a user by its username."""
        if not selectors.bug_is_fixed(3142, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3142')
        page = self.client.get(USER_PATH, params={
            'username': self.user['username']
        })
        for key, val in self.user.items():
            with self.subTest(key=key):
                self.assertEqual(page['results'][0][key], val)

    @selectors.skip_if(bool, 'user', False)
    def test_02_read_users(self):
        """Read all users. Verify that the created user is in the results."""
        users = [
            user for user in self.client.get(USER_PATH)['results']
            if user['_href'] == self.user['_href']
        ]
        self.assertEqual(len(users), 1, users)
        for key, val in users[0].items():
            with self.subTest(key=key):
                self.assertEqual(val, self.user[key])

    @selectors.skip_if(bool, 'user', False)
    def test_03_fully_update_user(self):
        """Update a user info using HTTP PUT."""
        attrs = _gen_verbose_user_attrs()
        if not selectors.bug_is_fixed(3125, self.cfg.pulp_version):
            attrs['username'] = self.user['username']
        self.client.put(self.user['_href'], attrs)
        user = self.client.get(self.user['_href'])
        for key, val in attrs.items():
            with self.subTest(key=key):
                if key == 'password':
                    self.assertNotIn(key, user)
                else:
                    self.assertEqual(user[key], val)

    @selectors.skip_if(bool, 'user', False)
    def test_03_partially_update_user(self):
        """Update a user info using HTTP PATCH."""
        attrs = _gen_verbose_user_attrs()
        if not selectors.bug_is_fixed(3125, self.cfg.pulp_version):
            del attrs['username']
        self.client.patch(self.user['_href'], attrs)
        user = self.client.get(self.user['_href'])
        for key, val in attrs.items():
            with self.subTest(key=key):
                if key == 'password':
                    self.assertNotIn(key, user)
                else:
                    self.assertEqual(user[key], val)

    @selectors.skip_if(bool, 'user', False)
    def test_04_delete_user(self):
        """Delete an user."""
        self.client.delete(self.user['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.user['_href'])


def _gen_verbose_user_attrs():
    """Generate a dict with lots of user attributes.

    For most tests, it's desirable to create users with as few attributes as
    possible, so that the tests can specifically target and attempt to break
    specific features. This module specifically targets users, so it makes
    sense to provide as many attributes as possible.
    """
    return {
        'username': utils.uuid4(),
        'password': utils.uuid4(),
    }
