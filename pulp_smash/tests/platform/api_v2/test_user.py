# coding=utf-8
"""Test the `user`_ API endpoints.

The assumptions explored in this module have the following dependencies::

    It is possible to create a user.
    ├── It is impossible to create a duplicate user.
    ├── It is possible to read a user.
    ├── It is possible to update a user.
    │   └── It is possible to search for a (updated) user.
    └── It is possible to delete a user.

.. _user:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/user/index.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from pulp_smash.constants import LOGIN_PATH, USER_PATH
from pulp_smash.utils import uuid4
from unittest2 import TestCase, skip


def _search_logins(response):
    """Return a tuple of all logins in a search response."""
    response.raise_for_status()
    return tuple(resp['login'] for resp in response.json())


class CreateTestCase(TestCase):
    """Establish that we can create users. No prior assumptions are made."""

    @classmethod
    def setUpClass(cls):
        """Create several users.

        Create one user with the minimum required attributes, and another with
        all available attributes.

        """
        cls.cfg = get_config()
        cls.bodies = (
            {'login': uuid4()},
            {key: uuid4() for key in {'login', 'password', 'name'}},
        )
        cls.responses = tuple((
            requests.post(
                cls.cfg.base_url + USER_PATH,
                json=body,
                **cls.cfg.get_requests_kwargs()
            )
            for body in cls.bodies
        ))

    def test_status_code(self):
        """Assert that each response has an HTTP 201 status code."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertEqual(response.status_code, 201)

    def test_password(self):
        """Assert that responses do not contain passwords."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertNotIn('password', response.json())

    def test_attrs(self):
        """Assert that each user has the requested attributes."""
        bodies = [body.copy() for body in self.bodies]  # Do not edit originals
        for body in bodies:
            body.pop('password', None)  # Pulp should not disclose passwords
        for i, body in enumerate(bodies):
            with self.subTest(body):
                # e.g. {'login'} <= {'login', 'name', '_href', …}
                attrs = self.responses[i].json()
                self.assertLessEqual(set(body.keys()), set(attrs.keys()))
                # Only check attributes we set. Ignore other returned attrs.
                attrs = {key: attrs[key] for key in body.keys()}
                self.assertEqual(body, attrs)

    @classmethod
    def tearDownClass(cls):
        """Delete the created users."""
        for response in cls.responses:
            requests.delete(
                cls.cfg.base_url + response.json()['_href'],
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()


class ReadUpdateDeleteTestCase(TestCase):
    """Establish that we can read, update and delete users.

    This test case assumes that the assertions in :class:`CreateTestCase` are
    valid.

    """

    @classmethod
    def setUpClass(cls):
        """Create three users and read, update and delete them respectively."""
        # Create three users and save the locations of each.
        cls.update_body = {'delta': {
            'name': uuid4(),
            'password': uuid4(),
            'roles': ['super-users'],
        }}
        cls.cfg = get_config()
        cls.paths = []
        for _ in range(3):
            response = requests.post(
                cls.cfg.base_url + USER_PATH,
                json={'login': uuid4()},
                **cls.cfg.get_requests_kwargs()
            )
            response.raise_for_status()
            cls.paths.append(response.json()['_href'])

        # Read, update and delete the three users, respectively.
        cls.read_response = requests.get(
            cls.cfg.base_url + cls.paths[0],
            **cls.cfg.get_requests_kwargs()
        )
        cls.update_response = requests.put(
            cls.cfg.base_url + cls.paths[1],
            json=cls.update_body,
            **cls.cfg.get_requests_kwargs()
        )
        cls.delete_response = requests.delete(
            cls.cfg.base_url + cls.paths[2],
            **cls.cfg.get_requests_kwargs()
        )

    def test_status_codes(self):
        """Ensure read, update and delete responses have 200 status codes."""
        for attr in ('read_response', 'update_response', 'delete_response'):
            with self.subTest(attr):
                self.assertEqual(getattr(self, attr).status_code, 200)

    def test_password_in_responses(self):
        """Ensure read and update responses do not contain a password.

        Target https://bugzilla.redhat.com/show_bug.cgi?id=1020300.

        """
        for response in (self.read_response, self.update_response):
            with self.subTest(response):
                self.assertNotIn('password', response.json())

    def test_use_deleted_user(self):
        """Assert that one cannot read, update or delete a deleted user."""
        # TODO asmacdo
        # http_actions = ('get', 'put', 'delete')
        http_actions = ('get', 'delete')
        responses = tuple((
            getattr(requests, http_action)(
                self.cfg.base_url + self.paths[-1],
                **self.cfg.get_requests_kwargs()
            )
            for http_action in http_actions
        ))
        for i, response in enumerate(responses):
            with self.subTest(http_actions[i]):
                self.assertEqual(response.status_code, 404)

    def test_updated_user(self):
        """Assert that the updated user has the assigned attributes."""
        attrs = self.update_response.json()
        for key in set(self.update_body['delta'].keys()) - {'password'}:
            with self.subTest(key):
                self.assertIn(key, attrs.keys())
                self.assertEqual(self.update_body['delta'][key], attrs[key])

    def test_updated_user_password(self):
        """Assert that one can log in with a user with an updated password."""
        login = self.update_response.json()['login']
        requests.post(
            self.cfg.base_url + LOGIN_PATH,
            auth=(login, self.update_body['delta']['password']),
            verify=self.cfg.verify,
        ).raise_for_status()

    def test_create_duplicate_user(self):
        """Verify that one cannot create a duplicate user."""
        response = requests.post(
            self.cfg.base_url + USER_PATH,
            json={'login': self.read_response.json()['login']},
            **self.cfg.get_requests_kwargs()
        )
        self.assertEqual(response.status_code, 409)

    @classmethod
    def tearDownClass(cls):
        """Delete created users.

        :meth:`setUpClass` makes a super-user. Thus, this method tests whether
        it is possible to delete a super-user.

        """
        for path in cls.paths[0:1]:
            requests.delete(
                cls.cfg.base_url + path,
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()


class SearchTestCase(TestCase):
    """Establish that we can search for users.

    This test case assumes that the assertions in
    :class:`ReadUpdateDeleteTestCase` are valid.

    """

    @classmethod
    def setUpClass(cls):
        """Create a user and add it to the 'super-users' role.

        Search for:

        * Nothing at all.
        * All users having only the super-users role.
        * All users having no roles.
        * A user by their login.
        * A non-existent user by their login.

        """
        # Create a user and note information about it.
        cls.cfg = get_config()
        cls.login = uuid4()
        response = requests.post(
            cls.cfg.base_url + USER_PATH,
            json={'login': cls.login},
            **cls.cfg.get_requests_kwargs()
        )
        response.raise_for_status()
        cls.path = response.json()['_href']

        # Make user a super-user.
        requests.put(
            cls.cfg.base_url + cls.path,
            json={'delta': {'roles': ['super-users']}},
            **cls.cfg.get_requests_kwargs()
        ).raise_for_status()

        # Formulate and execute searches. Save responses.
        searches = tuple((
            {'criteria': {}},
            {'criteria': {'filters': {'roles': ['super-users']}}},
            {'criteria': {'filters': {'roles': []}}},
            {'criteria': {'filters': {'login': cls.login}}},
            {'criteria': {'filters': {'login': uuid4()}}},
        ))
        cls.responses = tuple((
            requests.post(
                cls.cfg.base_url + USER_PATH + 'search/',
                json=search,
                **cls.cfg.get_requests_kwargs()
            )
            for search in searches
        ))

    def test_status_codes(self):
        """Assert that each response has an HTTP 200 status code."""
        for i, response in enumerate(self.responses):
            with self.subTest(i):
                self.assertEqual(response.status_code, 200, response.json())

    def test_global_search(self):
        """Assert that the global search includes the user's login."""
        self.assertIn(self.login, _search_logins(self.responses[0]))

    def test_roles_filter_inclusion(self):
        """Assert that the "roles" filter can be used for inclusion."""
        self.assertIn(self.login, _search_logins(self.responses[1]))

    def test_roles_filter_exclusion(self):
        """Assert that the "roles" filter can be used for exclusion."""
        self.assertNotIn(self.login, _search_logins(self.responses[2]))

    def test_login_filter_inclusion(self):
        """Search for a user via the "login" filter."""
        self.assertEqual({self.login}, set(_search_logins(self.responses[3])))

    def test_login_filter_exclusion(self):
        """Search for a non-existent user via the "login" filter."""
        self.assertEqual(len(_search_logins(self.responses[4])), 0)

    @classmethod
    def tearDownClass(cls):
        """Delete created users."""
        requests.delete(
            cls.cfg.base_url + cls.path,
            **cls.cfg.get_requests_kwargs()
        ).raise_for_status()
