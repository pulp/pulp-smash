# coding=utf-8
"""Tests that CRUD importers."""
import random
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import FILE_FEED_URL, FILE2_FEED_URL
from pulp_smash.tests.pulp3.constants import FILE_IMPORTER_PATH, REPO_PATH
from pulp_smash.tests.pulp3.file.api_v3.utils import gen_importer
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import get_auth


class CRUDImportersTestCase(unittest.TestCase, utils.SmokeTest):
    """CRUD importers."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        In order to create an importer a repository has to be created first.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.importer = {}
        cls.repo = cls.client.post(REPO_PATH, gen_repo())

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        cls.client.delete(cls.repo['_href'])

    def test_01_create_importer(self):
        """Create an importer."""
        body = _gen_verbose_importer()
        type(self).importer = self.client.post(FILE_IMPORTER_PATH, body)
        for key in ('username', 'password'):
            del body[key]
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.importer[key], val)

    @selectors.skip_if(bool, 'importer', False)
    def test_02_read_importer(self):
        """Read an importer by its href."""
        importer = self.client.get(self.importer['_href'])
        for key, val in self.importer.items():
            with self.subTest(key=key):
                self.assertEqual(importer[key], val)

    @selectors.skip_if(bool, 'importer', False)
    def test_02_read_importers(self):
        """Read an importer by its name."""
        page = self.client.get(FILE_IMPORTER_PATH, params={
            'name': self.importer['name']
        })
        self.assertEqual(len(page['results']), 1)
        for key, val in self.importer.items():
            with self.subTest(key=key):
                self.assertEqual(page['results'][0][key], val)

    @selectors.skip_if(bool, 'importer', False)
    def test_03_partially_update(self):
        """Update an importer using HTTP PATCH."""
        body = _gen_verbose_importer()
        self.client.patch(self.importer['_href'], body)
        for key in ('username', 'password'):
            del body[key]
        type(self).importer = self.client.get(self.importer['_href'])
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.importer[key], val)

    @selectors.skip_if(bool, 'importer', False)
    def test_04_fully_update(self):
        """Update an importer using HTTP PUT."""
        body = _gen_verbose_importer()
        self.client.put(self.importer['_href'], body)
        for key in ('username', 'password'):
            del body[key]
        type(self).importer = self.client.get(self.importer['_href'])
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.importer[key], val)

    @selectors.skip_if(bool, 'importer', False)
    def test_05_delete(self):
        """Delete an importer."""
        self.client.delete(self.importer['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.importer['_href'])


def _gen_verbose_importer():
    """Return a semi-random dict for use in defining an importer.

    For most tests, it's desirable to create importers with as few attributes
    as possible, so that the tests can specifically target and attempt to break
    specific features. This module specifically targets importers, so it makes
    sense to provide as many attributes as possible.

    Note that 'username' and 'password' are write-only attributes.
    """
    attrs = gen_importer()
    attrs.update({
        'feed_url': random.choice((FILE_FEED_URL, FILE2_FEED_URL)),
        'password': utils.uuid4(),
        'username': utils.uuid4(),
        'validate': random.choice((False, True)),
    })
    return attrs
