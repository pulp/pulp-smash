# coding=utf-8
"""Tests that sync file plugin repositories."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.constants import FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import FILE_IMPORTER_PATH, REPO_PATH
from pulp_smash.tests.pulp3.file.api_v3.utils import gen_importer
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import get_auth, sync_repo


class SyncFileRepoTestCase(unittest.TestCase):
    """Sync repositories with the file plugin."""

    def test_all(self):
        """Sync repositories with the file plugin..

        In order to sync a repository an importer has to be associated within
        this repository.
        When a repository is created this version field is set as None. After a
        sync the repository version is updated.

        Do the following:

        1. Create a repository, and an importer.
        2. Assert that repository version is None.
        3. Sync the importer.
        4. Assert that repository version is not None.
        5. Sync the importer one more time.
        6. Assert that repository version is different from the previous one.

        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        body = gen_importer(repo)
        body['feed_url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        importer = client.post(FILE_IMPORTER_PATH, body)
        self.addCleanup(client.delete, importer['_href'])

        # Sync the repository.
        self.assertEqual(repo['_latest_version_href'], None)
        sync_repo(cfg, importer)
        repo = client.get(repo['_href'])
        self.assertNotEqual(repo['_latest_version_href'], None)

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync_repo(cfg, importer)
        repo = client.get(repo['_href'])
        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
