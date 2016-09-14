# coding=utf-8
"""Test Pulp's `Searching`_ facilities.

The tests in this module make use of the `User APIs`_. However, few
user-specific references are made. These tests could be rewritten to use
repositories or something else with only minimal changes. Thus, the name of
this module.

Each test case executes one or more pairs of semantically identical POST and
GET requests. Each pair of search results should match exactly.

Most test cases assume that the assertions in some other test case hold true.
The assumptions explored in this module have the following dependencies::

    It is possible to ask for all resources of a kind.
    ├── It is possible to sort search results.
    ├── It is possible to ask for a single field in search results.
    ├── It is possible to ask for several fields in search results.
    └── It is possible to ask for a resource with a specific ID.
        └── It is possible to ask for a resource with one of several IDs.
            ├── It is possible to skip some search results.
            └── It is possible to limit how many search results are returned.

.. _Searching:
    https://docs.pulpproject.org/en/latest/dev-guide/conventions/criteria.html
.. _User APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/user/index.html
"""
import random
import unittest

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import USER_PATH
from pulp_smash.utils import uuid4


_SEARCH_PATH = USER_PATH + 'search/'
_USERS = []  # A list of dicts, each describing a user. See setUpModule.


def setUpModule():  # pylint:disable=invalid-name
    """Create several users, each with a randomized login name.

    Test cases may search for these users or otherwise perform non-destructive
    actions on them. Test cases should **not** change these users.
    """
    client = api.Client(config.get_config(), api.json_handler)
    del _USERS[:]  # Ensure idempotence
    for _ in range(3):
        _USERS.append(client.post(USER_PATH, {'login': uuid4()}))


def tearDownModule():  # pylint:disable=invalid-name
    """Delete the users created by :func:`setUpModule`."""
    client = api.Client(config.get_config())
    while _USERS:
        client.delete(_USERS.pop()['_href'])


class _BaseTestCase(utils.BaseAPITestCase):
    """Create an empty dict of searches, and add a common test method."""

    @classmethod
    def setUpClass(cls):
        """Create an empty dict of searches performed."""
        super(_BaseTestCase, cls).setUpClass()
        cls.searches = {}

    def test_status_code(self):
        """Assert each search has an HTTP 200 status code."""
        for key, response in self.searches.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 200)


class MinimalTestCase(_BaseTestCase):
    """Ask for all resources of a certain kind.

    ==== ====
    GET  no query parameters
    POST ``{'criteria': {}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Create one user. Execute searches."""
        super(MinimalTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.searches = {
            'get': client.get(_SEARCH_PATH),
            'post': client.post(_SEARCH_PATH, {'criteria': {}}),
        }

    def test_user_found(self):
        """Assert each search result should include a user we created."""
        for key, response in self.searches.items():
            with self.subTest(key=key):
                logins = {user['login'] for user in response.json()}
                self.assertIn(_USERS[0]['login'], logins)


class SortTestCase(_BaseTestCase):
    """Ask for sorted search results.

    There is no specification for executing these searches with GET.

    ==== ====
    POST ``{'criteria': {'sort': [['id', 'ascending']]}}``
    POST ``{'criteria': {'sort': [['id', 'descending']]}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Create two users. Execute searches."""
        super(SortTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        for order in {'ascending', 'descending'}:
            json = {'criteria': {'sort': [['id', order]]}}
            cls.searches['post_' + order] = client.post(_SEARCH_PATH, json)

    def test_ascending(self):
        """Assert ascending results are ordered from low to high."""
        results = self.searches['post_ascending'].json()
        ids = [result['_id']['$oid'] for result in results]
        self.assertEqual(ids, sorted(ids))

    def test_descending(self):
        """Assert descending results are ordered from high to low."""
        results = self.searches['post_descending'].json()
        ids = [result['_id']['$oid'] for result in results]
        self.assertEqual(ids, sorted(ids, reverse=True))


class FieldTestCase(_BaseTestCase):
    """Ask for a single field in search results.

    ==== ====
    GET  ``{'field': 'name'}`` (urlencoded)
    POST ``{'criteria': {'fields': 'name'}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Create one user. Execute searches."""
        super(FieldTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1933, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1933')
        client = api.Client(cls.cfg)
        cls.searches = {
            'get': client.get(_SEARCH_PATH, params={'field': 'name'}),
            'post': client.post(
                _SEARCH_PATH,
                {'criteria': {'fields': ['name']}},
            )
        }

    def test_field(self):
        """Only the requested key should be in each response."""
        for method, response in self.searches.items():
            with self.subTest(method=method):
                for result in response.json():  # for result in results:
                    self.assertEqual(set(result.keys()), {'name'}, result)


class FieldsTestCase(_BaseTestCase):
    """Ask for several fields in search results.

    ==== ====
    GET  ``field=login&field=roles``
    POST ``{'criteria': {'fields': ['login', 'roles']}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Create one user. Execute searches."""
        super(FieldsTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1933, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1933')
        client = api.Client(cls.cfg)
        cls.searches = {
            'get': client.get(_SEARCH_PATH, params='field=login&field=roles'),
            'post': client.post(
                _SEARCH_PATH,
                {'criteria': {'fields': ['login', 'roles']}},
            ),
        }

    def test_fields(self):
        """Only the requested keys should be in each response."""
        expected_keys = {'login', 'roles'}
        for method, response in self.searches.items():
            with self.subTest(method=method):
                for result in response.json():  # for result in results:
                    self.assertEqual(set(result.keys()), expected_keys, result)


class FiltersIdTestCase(_BaseTestCase):
    """Ask for a resource with a specific ID.

    There is no specification for executing these searches with GET.

    ==== ====
    GET  ``{'filters': {'id': '…'}}`` (urlencoded)
    POST ``{'criteria': {'filters': {'id': '…'}}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Search for exactly one user."""
        super(FiltersIdTestCase, cls).setUpClass()
        cls.user = random.choice(_USERS)
        json = {'criteria': {'filters': {'id': cls.user['id']}}}
        cls.searches['post'] = api.Client(cls.cfg).post(_SEARCH_PATH, json)

    def test_result_ids(self):
        """Assert the search results contain the correct IDs."""
        for method, response in self.searches.items():
            with self.subTest(method=method):
                ids = {result['_id']['$oid'] for result in response.json()}
                self.assertEqual({self.user['id']}, ids)


class FiltersIdsTestCase(_BaseTestCase):
    """Ask for resources with one of several IDs.

    There is no specification for executing these searches with GET.

    ==== ====
    GET  ``{'filters': {'id': {'$in': ['…', '…']}}}``
    POST ``{'criteria': {'filters': {'id': {'$in': ['…', '…']}}}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Search for exactly two users."""
        super(FiltersIdsTestCase, cls).setUpClass()
        cls.user_ids = [user['id'] for user in random.sample(_USERS, 2)]  # noqa pylint:disable=unsubscriptable-object
        cls.searches['post'] = api.Client(cls.cfg).post(
            _SEARCH_PATH,
            {'criteria': {'filters': {'id': {'$in': cls.user_ids}}}},
        )

    def test_result_ids(self):
        """Assert the search results contain the correct IDs."""
        for method, response in self.searches.items():
            with self.subTest(method=method):
                ids = {result['_id']['$oid'] for result in response.json()}
                self.assertEqual(set(self.user_ids), ids)


class LimitSkipTestCase(_BaseTestCase):
    """Ask for search results to be limited or skipped.

    There is no specification for executing these searches with GET.

    ==== ====
    GET  ``{'filters': {'id': {'$in': [id1, id2]}}, 'limit': 1}``
    GET  ``{'filters': {'id': {'$in': [id1, id2]}}, 'skip': 1}``
    POST ``{'criteria': {'filters': {'id': {'$in': [id1, id2]}}, 'limit': 1}}``
    POST ``{'criteria': {'filters': {'id': {'$in': [id1, id2]}}, 'skip': 1}}``
    ==== ====
    """

    @classmethod
    def setUpClass(cls):
        """Create two users. Execute searches."""
        super(LimitSkipTestCase, cls).setUpClass()
        cls.user_ids = [user['id'] for user in random.sample(_USERS, 2)]  # noqa pylint:disable=unsubscriptable-object
        client = api.Client(cls.cfg)
        for criterion in {'limit', 'skip'}:
            key = 'post_' + criterion
            query = {'filters': {'id': {'$in': cls.user_ids}}, criterion: 1}
            cls.searches[key] = client.post(_SEARCH_PATH, {'criteria': query})

    def test_results(self):
        """Check that one of the two created users has been found."""
        for key, response in self.searches.items():
            with self.subTest(key=key):
                ids = [result['_id']['$oid'] for result in response.json()]
                self.assertEqual(len(ids), 1, ids)
                self.assertIn(ids[0], self.user_ids)
