# coding=utf-8
"""Tests related to repository version."""
import unittest
from random import choice
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import FILE_FEED_COUNT, FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import FILE_IMPORTER_PATH, REPO_PATH
from pulp_smash.tests.pulp3.file.api_v3.utils import gen_importer
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import (
    get_added_content,
    get_auth,
    get_content,
    get_removed_content,
    sync_repo,
)


class AddRemoveContentTestCase(unittest.TestCase, utils.SmokeTest):
    """Add and remove content to a repository. Verify side-effects.

    A new repository version is automatically created each time content is
    added to or removed from a repository. Furthermore, it's possible to
    inspect any repository version and discover which content is present, which
    content was removed, and which content was added. This test case explores
    these features.

    This test targets the following issues:

    * `Pulp #3059 <https://pulp.plan.io/issues/3059>`_
    * `Pulp #3234 <https://pulp.plan.io/issues/3234>`_
    * `Pulp Smash #878 <https://github.com/PulpQE/pulp-smash/issues/878>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if selectors.bug_is_untestable(3502, cls.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/3502')
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.importer = {}
        cls.repo = {}
        cls.content = {}

    @classmethod
    def tearDownClass(cls):
        """Destroy resources created by test methods."""
        if cls.importer:
            cls.client.delete(cls.importer['_href'])
        if cls.repo:
            cls.client.delete(cls.repo['_href'])

    def test_01_create_repository(self):
        """Create a repository.

        Assert that:

        * The ``_versions_href`` API call is correct.
        * The ``_latest_version_href`` API call is correct.
        """
        self.repo.update(self.client.post(REPO_PATH, gen_repo()))

        repo_versions = self.client.get(self.repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 0)

        self.assertIsNone(self.repo['_latest_version_href'])

    @selectors.skip_if(bool, 'repo', False)
    def test_02_sync_content(self):
        """Sync content into the repository.

        Assert that:

        * The ``_versions_href`` API call is correct.
        * The ``_latest_version_href`` API call is correct.
        * The ``_latest_version_href + content/`` API call is correct.
        * The ``_latest_version_href + added_content/`` API call is correct.
        * The ``_latest_version_href + removed_content/`` API call is correct.
        * The ``content_summary`` attribute is correct.
        """
        body = gen_importer()
        body['feed_url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        self.importer.update(self.client.post(FILE_IMPORTER_PATH, body))
        sync_repo(self.cfg, self.importer, self.repo)
        repo = self.client.get(self.repo['_href'])

        repo_versions = self.client.get(repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 1)

        self.assertIsNotNone(repo['_latest_version_href'])

        content = get_content(repo)
        self.assertEqual(len(content['results']), FILE_FEED_COUNT)

        added_content = get_added_content(repo)
        self.assertEqual(len(added_content['results']), 3, added_content)

        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content['results']), 0, removed_content)

        content_summary = self.get_content_summary(repo)
        self.assertEqual(content_summary, {'file': FILE_FEED_COUNT})

    @selectors.skip_if(bool, 'repo', False)
    def test_03_remove_content(self):
        """Remove content from the repository.

        Make roughly the same assertions as :meth:`test_02_sync_content`.
        """
        repo = self.client.get(self.repo['_href'])
        self.content.update(choice(get_content(repo)['results']))
        self.client.post(
            repo['_versions_href'],
            {'remove_content_units': [self.content['_href']]}
        )
        repo = self.client.get(self.repo['_href'])

        repo_versions = self.client.get(repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 2)

        self.assertIsNotNone(repo['_latest_version_href'])

        content = get_content(repo)
        self.assertEqual(len(content['results']), FILE_FEED_COUNT - 1)

        added_content = get_added_content(repo)
        self.assertEqual(len(added_content['results']), 0, added_content)

        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content['results']), 1, removed_content)

        content_summary = self.get_content_summary(repo)
        self.assertEqual(content_summary, {'file': FILE_FEED_COUNT - 1})

    @selectors.skip_if(bool, 'repo', False)
    def test_04_add_content(self):
        """Add content to the repository.

        Make roughly the same assertions as :meth:`test_02_sync_content`.
        """
        repo = self.client.get(self.repo['_href'])
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [self.content['_href']]}
        )
        repo = self.client.get(self.repo['_href'])

        repo_versions = self.client.get(repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 3)

        self.assertIsNotNone(repo['_latest_version_href'])

        content = get_content(repo)
        self.assertEqual(len(content['results']), FILE_FEED_COUNT)

        added_content = get_added_content(repo)
        self.assertEqual(len(added_content['results']), 1, added_content)

        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content['results']), 0, removed_content)

        content_summary = self.get_content_summary(repo)
        self.assertEqual(content_summary, {'file': FILE_FEED_COUNT})

    def get_content_summary(self, repo):
        """Get the ``content_summary`` for the given repository."""
        repo_versions = self.client.get(repo['_versions_href'])
        content_summaries = [
            repo_version['content_summary']
            for repo_version in repo_versions['results']
            if repo_version['_href'] == repo['_latest_version_href']
        ]
        self.assertEqual(len(content_summaries), 1, content_summaries)
        return content_summaries[0]
