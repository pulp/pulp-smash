# coding=utf-8
"""Test Pulp's `Searching`_ facilities.

The test cases in this module searches for content units by their type. See:

* `Pulp Smash #133`_ asks for tests showing that it's possible to search for
  content units by their type.
* The `Search for Units`_ API documentation is relevant.

.. _Pulp Smash #133: https://github.com/PulpQE/pulp-smash/issues/133
.. _Search for Units:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/units.html#search-for-units
.. _Searching:
    http://docs.pulpproject.org/en/latest/dev-guide/conventions/criteria.html
"""
import inspect
import unittest
from urllib.parse import urljoin

from pulp_smash import api, utils
from pulp_smash.constants import (
    CONTENT_UNITS_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_SIGNED_FEED_URL,
    SRPM,
    SRPM_SIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import check_issue_2620
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class BaseSearchTestCase(utils.BaseAPITestCase):
    """Provide common functionality for the other test cases in this module."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository."""
        if inspect.getmro(cls)[0] == BaseSearchTestCase:
            raise unittest.SkipTest('Abstract base class.')
        super(BaseSearchTestCase, cls).setUpClass()
        if check_issue_2620(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')
        body = gen_repo()
        body['importer_config']['feed'] = cls.get_feed_url()
        cls.repo = api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()
        cls.resources.add(cls.repo['_href'])
        utils.sync_repo(cls.cfg, cls.repo)

    @staticmethod
    def get_feed_url():
        """Return a repository feed URL. Used by :meth:`setUpClass`.

        All child classes should override this method.
        """
        raise NotImplementedError('Please provide a repository feed URL.')

    def get_unit_by_filename(self, units, filename):
        """Return the unit with the given filename.

        Test methods in child classes may find this method to be of use.

        :param units: An iterable of SRPM content units.
        :param filename: The filename of one of the content units.
        :returns: The content unit with the given filename.
        :raises: An assertion error if more or less than one matching unit is
            found.
        """
        matches = [unit for unit in units if unit['filename'] == filename]
        self.assertEqual(len(matches), 1, matches)
        return matches[0]


class SearchForRpmTestCase(BaseSearchTestCase):
    """Search for ``rpm`` content units in several different ways."""

    @staticmethod
    def get_feed_url():
        """Return an RPM repository feed URL."""
        return RPM_SIGNED_FEED_URL

    def test_search_for_all(self):
        """Search for all "rpm" units.

        Perform the following searches. Assert a unit with filename
        :data:`pulp_smash.constants.RPM` is in the search results.

        ==== ====================
        GET  n/a
        POST ``{'criteria': {}}``
        ==== ====================
        """
        def verify(units):
            """Make assertions about search results."""
            self.get_unit_by_filename(units, RPM)

        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(CONTENT_UNITS_PATH, 'rpm/search/')
        with self.subTest(method='get'):
            verify(client.get(path))
        with self.subTest(method='post'):
            verify(client.post(path, {'criteria': {}}))

    def test_include_repos(self):
        """Search for all "rpm" units, and include repos in the results.

        Perform the following searches. Assert a unit with filename
        :data:`pulp_smash.constants.RPM` is in the search results, and assert
        it belongs to the repository created in
        :meth:`BaseSearchTestCase.setUpClass`.

        ==== ====================
        GET  ``{'include_repos': True}`` (urlencoded)
        POST ``{'criteria': {}, 'include_repos': True}``
        ==== ====================
        """
        def verify(units):
            """Make assertions about search results."""
            unit = self.get_unit_by_filename(units, RPM)
            self.assertIn(self.repo['id'], unit['repository_memberships'])

        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(CONTENT_UNITS_PATH, 'rpm/search/')
        with self.subTest(method='get'):
            verify(client.get(path, params={'include_repos': True}))
        with self.subTest(method='post'):
            verify(client.post(path, {'criteria': {}, 'include_repos': True}))


class SearchForSrpmTestCase(BaseSearchTestCase):
    """Search for ``srpm`` content units in several different ways."""

    @staticmethod
    def get_feed_url():
        """Return an RPM repository feed URL."""
        return SRPM_SIGNED_FEED_URL

    def test_search_for_all(self):
        """Search for all "srpm" units.

        Perform the following searches. Assert a unit with filename
        :data:`pulp_smash.constants.SRPM` is in the search results.

        ==== ====================
        GET  n/a
        POST ``{'criteria': {}}``
        ==== ====================
        """
        def verify(units):
            """Make assertions about search results."""
            self.get_unit_by_filename(units, SRPM)

        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(CONTENT_UNITS_PATH, 'srpm/search/')
        with self.subTest(method='get'):
            verify(client.get(path))
        with self.subTest(method='post'):
            verify(client.post(path, {'criteria': {}}))

    def test_include_repos(self):
        """Search for all "srpm" units, and include repos in the results.

        Perform the following searches. Assert a unit with filename
        :data:`pulp_smash.constants.SRPM` is in the search results, and assert
        it belongs to the repository created in
        :meth:`BaseSearchTestCase.setUpClass`.

        ==== ====================
        GET  ``{'include_repos': True}`` (urlencoded)
        POST ``{'criteria': {}, 'include_repos': True}``
        ==== ====================
        """
        def verify(units):
            """Make assertions about search results."""
            unit = self.get_unit_by_filename(units, SRPM)
            self.assertIn(self.repo['id'], unit['repository_memberships'])

        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(CONTENT_UNITS_PATH, 'srpm/search/')
        with self.subTest(method='get'):
            verify(client.get(path, params={'include_repos': True}))
        with self.subTest(method='post'):
            verify(client.post(path, {'criteria': {}, 'include_repos': True}))
