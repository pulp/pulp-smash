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
    https://pulp.readthedocs.org/en/latest/dev-guide/conventions/criteria.html
.. _User APIs:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/user/index.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from pulp_smash.constants import USER_PATH
from pulp_smash.utils import create_user, delete, uuid4
from unittest2 import TestCase, skip

from sys import version_info
if version_info.major == 2:
    from urllib import urlencode  # pylint:disable=no-name-in-module
else:
    from urllib.parse import urlencode  # noqa pylint:disable=no-name-in-module,import-error


_SEARCH_PATH = USER_PATH + 'search/'


def _create_users(server_config, num):
    """Create ``num`` users with random logins. Return tuple of attributes."""
    return tuple((
        create_user(server_config, {'login': uuid4()}) for _ in range(num)
    ))


def _search_get(server_config, query):
    """Search for users. ``query`` may be a raw query string or a dict."""
    if isinstance(query, dict):
        query = '?' + urlencode(query)
    return requests.get(
        server_config.base_url + _SEARCH_PATH + query,
        **server_config.get_requests_kwargs()
    )


def _search_post(server_config, json):
    """Search for users. ``json`` must be a JSON-encodable object."""
    return requests.post(
        server_config.base_url + _SEARCH_PATH,
        json=json,
        **server_config.get_requests_kwargs()
    )


class _BaseTestCase(TestCase):
    """Provides functionality common to most test cases in this module."""

    @classmethod
    def setUpClass(cls):
        """Set default values for the other methods on this class."""
        cls.cfg = get_config()
        cls.attrs_iter = ()  # ({'login': …, '_href': …}, {…})
        cls.responses = {}  # {'get': …, 'post': …}

    def test_status_code(self):
        """All responses should have HTTP 200 status codes."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                self.assertEqual(response.status_code, 200)

    @classmethod
    def tearDownClass(cls):
        """Destroy all resources created in :meth:`setUpClass`."""
        for attrs in cls.attrs_iter:
            delete(cls.cfg, attrs['_href'])


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
        cls.attrs_iter = _create_users(cls.cfg, 1)
        cls.responses = {
            'get': _search_get(cls.cfg, ''),
            'post': _search_post(cls.cfg, {'criteria': {}}),
        }

    def test_user_found(self):
        """All responses should include the user we created."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                response.raise_for_status()
                self.assertIn(
                    self.attrs_iter[0]['login'],
                    {user['login'] for user in response.json()}
                )


class SortTestCase(_BaseTestCase):
    """Ask for sorted search results.

    ==== ====
    POST ``{'criteria': {'sort': [['id', 'ascending']]}}``
    POST ``{'criteria': {'sort': [['id', 'descending']]}}``
    ==== ====

    """

    @classmethod
    def setUpClass(cls):
        """Create two users. Execute searches."""
        super(SortTestCase, cls).setUpClass()
        cls.attrs_iter = _create_users(cls.cfg, 2)
        for order in ('ascending', 'descending'):
            query = {'sort': [['id', order]]}
            cls.responses.update({
                # No specification exists for these GET searches.
                # 'get_' + order: _search_get(cls.cfg, 'unknown query'),
                'post_' + order: _search_post(cls.cfg, {'criteria': query}),
            })

    def test_ascending(self):
        """Ensure that ascending results are ordered from low to high."""
        response = self.responses['post_ascending']
        response.raise_for_status()
        ids = [attrs['_id']['$oid'] for attrs in response.json()]
        self.assertEqual(ids, sorted(ids))

    def test_descending(self):
        """Ensure that descending results are ordered from high to low."""
        response = self.responses['post_descending']
        response.raise_for_status()
        ids = [attrs['_id']['$oid'] for attrs in response.json()]
        self.assertEqual(ids, sorted(ids, reverse=True))


@skip('See: https://pulp.plan.io/issues/1332')
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
        cls.attrs_iter = _create_users(cls.cfg, 1)
        cls.responses = {
            'get': _search_get(cls.cfg, '?field=name'),
            'post': _search_post(cls.cfg, {'criteria': {'fields': ['name']}}),
        }

    def test_field(self):
        """Only the requested key should be in each response."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                response.raise_for_status()
                for attrs in response.json():
                    self.assertEqual(set(attrs.keys()), {'name'})


@skip('See: https://pulp.plan.io/issues/1332')
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
        cls.attrs_iter = _create_users(cls.cfg, 1)
        cls.responses = {
            'get': _search_get(cls.cfg, '?field=login&field=roles'),
            'post': _search_post(
                cls.cfg,
                {'criteria': {'fields': ['login', 'roles']}},
            ),
        }

    def test_fields(self):
        """Only the requested keys should be in each response."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                response.raise_for_status()
                for attrs in response.json():
                    self.assertEqual(set(attrs.keys()), {'login', 'roles'})


class FiltersIdTestCase(_BaseTestCase):
    """Ask for a resource with a specific ID.

    ==== ====
    GET  ``{'filters': {'id': '…'}}`` (urlencoded)
    POST ``{'criteria': {'filters': {'id': '…'}}}``
    ==== ====

    """

    @classmethod
    def setUpClass(cls):
        """Create two users. Search for one user."""
        super(FiltersIdTestCase, cls).setUpClass()
        cls.attrs_iter = _create_users(cls.cfg, 2)
        cls.id_ = cls.attrs_iter[0]['id']
        query = {'filters': {'id': cls.id_}}
        cls.responses = {
            # No specification exists for these GET searches.
            # 'get': _search_get(cls.cfg, 'unknown query'),
            'post': _search_post(cls.cfg, {'criteria': query}),
        }

    def test_result_ids(self):
        """Check that the results have the correct IDs."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                response.raise_for_status()
                self.assertEqual(
                    {attrs['_id']['$oid'] for attrs in response.json()},
                    {self.id_}
                )


class FiltersIdsTestCase(_BaseTestCase):
    """Ask for resources with one of several IDs.

    ==== ====
    GET  ``{'filters': {'id': {'$in': ['…', '…']}}}``
    POST ``{'criteria': {'filters': {'id': {'$in': ['…', '…']}}}}``
    ==== ====

    """

    @classmethod
    def setUpClass(cls):
        """Create three users. Search for the first two users."""
        super(FiltersIdsTestCase, cls).setUpClass()
        cls.attrs_iter = _create_users(cls.cfg, 3)
        cls.ids = [attrs['id'] for attrs in cls.attrs_iter[0:1]]
        query = {'filters': {'id': {'$in': cls.ids}}}
        cls.responses = {
            # No specification exists for these GET searches.
            # 'get': _search_get(cls.cfg, 'unknown query'),
            'post': _search_post(cls.cfg, {'criteria': query}),
        }

    def test_result_ids(self):
        """Check that the results have the correct IDs."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                response.raise_for_status()
                self.assertEqual(
                    {attrs['_id']['$oid'] for attrs in response.json()},
                    set(self.ids),
                )


class LimitSkipTestCase(_BaseTestCase):
    """Ask for search results to be limited or skipped.

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
        cls.attrs_iter = _create_users(cls.cfg, 2)
        cls.ids = [attrs['id'] for attrs in cls.attrs_iter]
        for criterion in ('limit', 'skip'):
            query = {'filters': {'id': {'$in': cls.ids}}, criterion: 1}
            cls.responses.update({
                # No specification exists for these GET searches.
                # 'get_' + criterion: _search_get(cls.cfg, 'unknown query'),
                'post_' + criterion: _search_post(cls.cfg, {'criteria': query})
            })

    def test_results(self):
        """Check that one of the two created users has been found."""
        for action, response in self.responses.items():
            with self.subTest(action=action):
                response.raise_for_status()
                # The search should yield one of the two users created.
                found_ids = [attrs['_id']['$oid'] for attrs in response.json()]
                self.assertEqual(len(found_ids), 1, found_ids)
                self.assertIn(found_ids[0], self.ids)
