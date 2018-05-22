# coding=utf-8
"""Tests that CRUD distributions."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import DISTRIBUTION_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_smash.tests.pulp3.utils import gen_distribution, get_auth
from pulp_smash.utils import uuid4


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
        """Read a distribution using query parameters."""
        if selectors.bug_is_untestable(3082, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3082')
        for params in (
                {'name': self.distribution['name']},
                {'base_path': self.distribution['base_path']}):
            with self.subTest(params=params):
                page = self.client.get(DISTRIBUTION_PATH, params=params)
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


class DistributionBasePathTestCase(unittest.TestCase):
    """Test possible values for ``base_path`` on a distribution.

    This test targets the following issues:

    * `Pulp #3412 <https://pulp.plan.io/issues/3412>`_
    * `Pulp Smash #906 <https://github.com/PulpQE/pulp-smash/issues/906>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.distribution = cls.client.post(DISTRIBUTION_PATH, gen_distribution())

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        cls.client.delete(cls.distribution['_href'])

    def test_spaces(self):
        """Test that spaces can not be part of ``base_path``."""
        self.try_create_distribution(base_path=uuid4().replace('-', ' '))
        self.try_update_distribution(base_path=uuid4().replace('-', ' '))

    def test_begin_slash(self):
        """Test that slash cannot be in the begin of ``base_path``."""
        self.try_create_distribution(base_path='/' + uuid4())
        self.try_update_distribution(base_path='/' + uuid4())

    def test_end_slash(self):
        """Test that slash cannot be in the end of ``base_path``."""
        self.try_create_distribution(base_path=uuid4() + '/')
        self.try_update_distribution(base_path=uuid4() + '/')

    def test_unique_base_path(self):
        """Test that ``base_path`` can not be duplicated."""
        self.try_create_distribution(base_path=self.distribution['base_path'])

    def try_create_distribution(self, **kwargs):
        """Unsuccessfully create a distribution.

        Merge the given kwargs into the body of the request.
        """
        body = gen_distribution()
        body.update(kwargs)
        with self.assertRaises(HTTPError):
            self.client.post(DISTRIBUTION_PATH, body)

    def try_update_distribution(self, **kwargs):
        """Unsuccessfully update a distribution with HTTP PATCH.

        Use the given kwargs as the body of the request.
        """
        with self.assertRaises(HTTPError):
            self.client.patch(self.distribution['_href'], kwargs)
