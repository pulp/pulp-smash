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
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/user/index.html
"""
from pulp_smash import api, utils
from pulp_smash.constants import LOGIN_PATH, USER_PATH


def _logins(search_response):
    """Return a set of all logins in a search response."""
    return {resp['login'] for resp in search_response.json()}


class CreateTestCase(utils.BaseAPITestCase):
    """Establish that we can create users. No prior assumptions are made."""

    @classmethod
    def setUpClass(cls):
        """Create several users.

        Create one user with the minimum required attributes, and another with
        all available attributes.
        """
        super(CreateTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.bodies = (
            {'login': utils.uuid4()},
            {key: utils.uuid4() for key in {'login', 'password', 'name'}},
        )
        cls.responses = []
        for body in cls.bodies:
            response = client.post(USER_PATH, body)
            cls.responses.append(response)
            cls.resources.add(response.json()['_href'])  # See parent class

    def test_status_code(self):
        """Assert that each response has an HTTP 201 status code."""
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                self.assertEqual(response.status_code, 201)

    def test_password(self):
        """Assert that responses do not contain passwords."""
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                self.assertNotIn('password', response.json())

    def test_attrs(self):
        """Assert that each user has the requested attributes."""
        bodies = [body.copy() for body in self.bodies]  # Do not edit originals
        for body in bodies:
            body.pop('password', None)
        for body, response in zip(bodies, self.responses):
            with self.subTest(body=body):
                attrs = response.json()
                # e.g. {'login'} <= {'login', 'name', '_href', …}
                self.assertLessEqual(set(body.keys()), set(attrs.keys()))
                # Only check attributes we set. Ignore other returned attrs.
                attrs = {key: attrs[key] for key in body.keys()}
                self.assertEqual(body, attrs)


class ReadUpdateDeleteTestCase(utils.BaseAPITestCase):
    """Establish that we can read, update and delete users.

    This test case assumes that the assertions in :class:`CreateTestCase` are
    valid.
    """

    @classmethod
    def setUpClass(cls):
        """Create three users and read, update and delete them respectively."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()

        # Create three users and save their attributes.
        client = api.Client(cls.cfg, response_handler=api.json_handler)
        hrefs = [
            client.post(USER_PATH, {'login': utils.uuid4()})['_href']
            for _ in range(3)
        ]

        # Read, update and delete the users, and save the raw responses.
        client.response_handler = api.safe_handler
        cls.update_body = {'delta': {
            'name': utils.uuid4(),
            'password': utils.uuid4(),
            'roles': ['super-users'],
        }}
        cls.responses = {}
        cls.responses['read'] = client.get(hrefs[0])
        cls.responses['update'] = client.put(hrefs[1], cls.update_body)
        cls.responses['delete'] = client.delete(hrefs[2])

        # Read, update and delete the deleted user, and save the raw responses.
        client.response_handler = api.echo_handler
        cls.responses['read deleted'] = client.get(hrefs[2])
        cls.responses['update deleted'] = client.put(hrefs[2], {})
        cls.responses['delete deleted'] = client.delete(hrefs[2])

        # Mark resources to be deleted.
        cls.resources = {hrefs[0], hrefs[1]}

    def test_status_code(self):
        """Ensure read, update and delete responses have 200 status codes."""
        for response in ('read', 'update', 'delete'):
            with self.subTest(response=response):
                self.assertEqual(self.responses[response].status_code, 200)

    def test_password_not_in_response(self):
        """Ensure read and update responses do not contain a password.

        Target https://bugzilla.redhat.com/show_bug.cgi?id=1020300.
        """
        for response in ('read', 'update'):
            with self.subTest(response=response):
                self.assertNotIn('password', self.responses[response].json())

    def test_use_deleted_user(self):
        """Assert one cannot read, update or delete a deleted user."""
        for response in ('read deleted', 'update deleted', 'delete deleted'):
            with self.subTest(response=response):
                self.assertEqual(self.responses[response].status_code, 404)

    def test_updated_user(self):
        """Assert the updated user has the assigned attributes."""
        delta = self.update_body['delta'].copy()  # we sent this
        del delta['password']
        attrs = self.responses['update'].json()  # the server responded w/this
        self.assertLessEqual(set(delta.keys()), set(attrs.keys()))
        attrs = {key: attrs[key] for key in delta.keys()}
        self.assertEqual(delta, attrs)

    def test_updated_user_password(self):
        """Assert one can log in with a user with an updated password."""
        auth = (
            self.responses['update'].json()['login'],
            self.update_body['delta']['password'],
        )
        api.Client(self.cfg).post(LOGIN_PATH, auth=auth)

    def test_create_duplicate_user(self):
        """Verify one cannot create a user with a duplicate login."""
        json = {'login': self.responses['read'].json()['login']}
        response = api.Client(self.cfg, api.echo_handler).post(USER_PATH, json)
        self.assertEqual(response.status_code, 409)


class SearchTestCase(utils.BaseAPITestCase):
    """Establish we can search for users.

    This test case assumes the assertions in :class:`ReadUpdateDeleteTestCase`
    are valid.
    """

    @classmethod
    def setUpClass(cls):
        """Create a user and add it to the 'super-users' role.

        Search for:

        * Nothing at all:
        * All users having only the super-users role.
        * All users having no roles.
        * A user by their login.
        * A non-existent user by their login.
        """
        super(SearchTestCase, cls).setUpClass()

        # Create a super-user.
        client = api.Client(cls.cfg, response_handler=api.json_handler)
        cls.user = client.post(USER_PATH, {'login': utils.uuid4()})
        client.put(cls.user['_href'], {'delta': {'roles': ['super-users']}})
        cls.user = client.get(cls.user['_href'])

        # Formulate and execute searches, and save raw responses.
        client.response_handler = api.safe_handler
        cls.searches = tuple((
            {'criteria': {}},
            {'criteria': {'filters': {'roles': ['super-users']}}},
            {'criteria': {'filters': {'roles': []}}},
            {'criteria': {'filters': {'login': cls.user['login']}}},
            {'criteria': {'filters': {'login': utils.uuid4()}}},
        ))
        cls.responses = tuple((
            client.post(USER_PATH + 'search/', search)
            for search in cls.searches
        ))

    def test_status_codes(self):
        """Assert each response has an HTTP 200 status code."""
        for search, response in zip(self.searches, self.responses):
            with self.subTest(search=search):
                self.assertEqual(response.status_code, 200)

    def test_global_search(self):
        """Assert the global search includes our user."""
        self.assertIn(self.user['login'], _logins(self.responses[0]))

    def test_roles_filter_inclusion(self):
        """Assert that the "roles" filter can be used for inclusion."""
        self.assertIn(self.user['login'], _logins(self.responses[1]))

    def test_roles_filter_exclusion(self):
        """Assert that the "roles" filter can be used for exclusion."""
        self.assertNotIn(self.user['login'], _logins(self.responses[2]))

    def test_login_filter_inclusion(self):
        """Search for a user via the "login" filter."""
        self.assertEqual({self.user['login']}, _logins(self.responses[3]))

    def test_login_filter_exclusion(self):
        """Search for a non-existent user via the "login" filter."""
        self.assertEqual(len(_logins(self.responses[4])), 0)
