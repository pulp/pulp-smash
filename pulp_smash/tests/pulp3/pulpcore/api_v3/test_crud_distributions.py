# coding=utf-8
"""Tests that CRUD distributions."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import DISTRIBUTION_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import gen_distribution
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.utils import get_auth


class CRUDDistributionsTestCase(unittest.TestCase, utils.SmokeTest):
    """CRUD distributions."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.distribution = {}

    def test_01_create_distribution(self):
        """Create a distribution."""
        body = gen_distribution()
        type(self).distribution = self.client.post(DISTRIBUTION_PATH, body)
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.distribution[key], val)

    @selectors.skip_if(bool, 'distribution', False)
    def test_02_read_distribution(self):
        """Read a distribution by its _href."""
        distribution = self.client.get(self.distribution['_href'])
        for key, val in self.distribution.items():
            with self.subTest(key=key):
                self.assertEqual(distribution[key], val)

    @selectors.skip_if(bool, 'distribution', False)
    def test_02_read_distributions(self):
        """Read a distribution by its name."""
        if selectors.bug_is_untestable(3082, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3082')
        page = self.client.get(DISTRIBUTION_PATH, params={
            'name': self.distribution['name']
        })
        self.assertEqual(len(page['results']), 1)
        for key, val in self.distribution.items():
            with self.subTest(key=key):
                self.assertEqual(page['results'][0][key], val)

    @selectors.skip_if(bool, 'distribution', False)
    def test_03_partially_update(self):
        """Update a distribution using HTTP PATCH."""
        body = gen_distribution()
        self.client.patch(self.distribution['_href'], body)
        type(self).distribution = self.client.get(self.distribution['_href'])
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.distribution[key], val)

    @selectors.skip_if(bool, 'distribution', False)
    def test_04_fully_update(self):
        """Update a distribution using HTTP PUT."""
        body = gen_distribution()
        self.client.put(self.distribution['_href'], body)
        type(self).distribution = self.client.get(self.distribution['_href'])
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.distribution[key], val)

    @selectors.skip_if(bool, 'distribution', False)
    def test_05_delete(self):
        """Delete a distribution."""
        self.client.delete(self.distribution['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.distribution['_href'])
