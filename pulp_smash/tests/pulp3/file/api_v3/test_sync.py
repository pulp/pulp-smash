# coding=utf-8
"""Tests that sync file plugin repositories."""
import unittest
from itertools import product
from urllib.parse import urljoin

from pulp_smash import api, config, selectors
from pulp_smash.constants import FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import (
    FILE_IMPORTER_PATH,
    IMPORTER_DOWN_POLICY,
    IMPORTER_SYNC_MODE,
    REPO_PATH,
)
from pulp_smash.tests.pulp3.file.api_v3.utils import gen_importer
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import get_auth, sync_repo


class SyncFileRepoTestCase(unittest.TestCase):
    """Sync repositories with the file plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()

    def test_all(self):
        """Call :meth:`do_test` with varying arguments.

        Call :meth:`do_test` with each possible pairing of
        :data:`pulp_smash.tests.pulp3.constants.IMPORTER_DOWN_POLICY` and
        :data:`pulp_smash.tests.pulp3.constants.IMPORTER_SYNC_MODE`. If `Pulp
        #3320`_ affects Pulp, then the ``background`` and ``on_demand``
        download policies are omitted from the test matrix.

        .. _Pulp #3320: https://pulp.plan.io/issues/3320
        """
        importer_down_policy = IMPORTER_DOWN_POLICY
        if selectors.bug_is_untestable(3320, self.cfg):
            importer_down_policy -= {'background', 'on_demand'}
        for pair in product(importer_down_policy, IMPORTER_SYNC_MODE):
            with self.subTest(pair=pair):
                self.do_test(*pair)

    def do_test(self, download_policy, sync_mode):
        """Sync repositories with the file plugin.

        In order to sync a repository an importer has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository, and an importer.
        2. Assert that repository version is None.
        3. Sync the importer.
        4. Assert that repository version is not None.
        5. Sync the importer one more time.
        6. Assert that repository version is different from the previous one.

        :param download_policy: The download policy for the importer.
        :param sync_mode: The sync mode for the importer.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        body = gen_importer(repo)
        body['download_policy'] = download_policy
        body['feed_url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        body['sync_mode'] = sync_mode
        importer = client.post(FILE_IMPORTER_PATH, body)
        self.addCleanup(client.delete, importer['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync_repo(self.cfg, importer)
        repo = client.get(repo['_href'])
        self.assertIsNotNone(repo['_latest_version_href'])

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync_repo(self.cfg, importer)
        repo = client.get(repo['_href'])
        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
