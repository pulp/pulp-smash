# coding=utf-8
"""Tests related to pagination."""
import unittest
from random import randint, sample
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.constants import FILE_MANY_FEED_COUNT, FILE_MANY_FEED_URL
from pulp_smash.tests.pulp3.file.utils import populate_pulp
from pulp_smash.pulp3.constants import FILE_CONTENT_PATH, REPO_PATH
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content,
    get_auth,
    get_content,
    get_removed_content,
    get_versions,
)


class PaginationTestCase(unittest.TestCase):
    """Test pagination."""

    # pylint:disable=unsubscriptable-object
    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.page_handler)
        cls.client.request_kwargs['auth'] = get_auth(cls.cfg)
        populate_pulp(cls.cfg, urljoin(FILE_MANY_FEED_URL, 'PULP_MANIFEST'))

    def test_repos(self):
        """Test pagination for repositories."""
        number_of_repos = randint(100, 150)
        for _ in range(number_of_repos):
            repo = self.client.post(REPO_PATH, gen_repo())
            self.addCleanup(self.client.delete, repo['_href'])
        repos = self.client.get(REPO_PATH)
        self.assertEqual(len(repos), number_of_repos, repos)

    def test_content(self):
        """Test pagination for different endpoints.

        Test pagination for repository versions, added and removed content.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        contents = sample(self.client.get(FILE_CONTENT_PATH), FILE_MANY_FEED_COUNT)
        for content in contents:
            self.client.post(
                repo['_versions_href'],
                {'add_content_units': [content['_href']]}
            )
        repo = self.client.get(repo['_href'])
        repo_versions = get_versions(repo)
        self.assertEqual(len(repo_versions), FILE_MANY_FEED_COUNT, repo_versions)
        content = get_content(repo)
        self.assertEqual(len(content), FILE_MANY_FEED_COUNT, content)
        added_content = get_added_content(repo)
        self.assertEqual(len(added_content), 1, added_content)
        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content), 0, removed_content)
