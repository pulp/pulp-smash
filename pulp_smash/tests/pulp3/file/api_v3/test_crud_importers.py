# coding=utf-8
"""Tests that CRUD importers."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors
from pulp_smash.tests.pulp3.constants import FILE_IMPORTER_PATH, REPO_PATH
from pulp_smash.tests.pulp3.file.api_v3.utils import (
    gen_importer,
    modify_importer_down_policy,
    modify_importer_sync_mode,
)
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import get_auth


class CRUDImportersTestCase(unittest.TestCase):
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

    @selectors.skip_if(bool, 'repo', False)
    def test_01_create_importer(self):
        """Create an importer."""
        body = gen_importer()
        body['repository'] = self.repo['_href']
        type(self).importer = self.client.post(FILE_IMPORTER_PATH, body)

    @selectors.skip_if(bool, 'importer', False)
    def test_02_read_importer(self):
        """Read an importer by its href."""
        importer = self.client.get(self.importer['_href'])
        self.assertEqual(self.importer['name'], importer['name'])

    @selectors.skip_if(bool, 'importer', False)
    def test_02_read_importers(self):
        """Read an importer by its name."""
        page = self.client.get(FILE_IMPORTER_PATH, params={
            'name': self.importer['name']
        })
        self.assertEqual(len(page['results']), 1)
        self.assertEqual(page['results'][0]['name'], self.importer['name'])

    @selectors.skip_if(bool, 'importer', False)
    def test_03_partially_update(self):
        """Update an importer using HTTP PATCH."""
        attr = {
            'download_policy': modify_importer_down_policy(
                {self.importer['download_policy']}
            ),
            'sync_mode': modify_importer_sync_mode(
                {self.importer['sync_mode']}
            )
        }
        self.client.patch(self.importer['_href'], attr)
        importer = self.client.get(self.importer['_href'])
        self.assertEqual(attr['download_policy'], importer['download_policy'])
        self.assertEqual(attr['sync_mode'], importer['sync_mode'])

    @selectors.skip_if(bool, 'importer', False)
    def test_04_fully_update(self):
        """Update an importer using HTTP PUT."""
        body = gen_importer()
        body['repository'] = self.importer['repository']
        self.client.put(self.importer['_href'], body)
        type(self).importer = self.client.get(self.importer['_href'])
        self.addCleanup(self.client.delete, self.importer['_href'])

        self.assertEqual(body['name'], self.importer['name'])
        self.assertEqual(
            body['download_policy'],
            self.importer['download_policy']
        )
        self.assertEqual(body['sync_mode'], self.importer['sync_mode'])

    @selectors.skip_if(bool, 'importer', False)
    def test_05_delete(self):
        """Delete an importer."""
        self.doCleanups()

        # Verify importer was deleted.
        with self.assertRaises(HTTPError):
            self.client.get(self.importer['_href'])
