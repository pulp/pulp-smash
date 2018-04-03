# coding=utf-8
"""Tests related to repository version."""
import unittest
from random import choice, randint
from urllib.parse import urljoin

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    FILE_FEED_COUNT,
    FILE_FEED_URL,
    FILE_LARGE_FEED_URL,
)

from pulp_smash.tests.pulp3.constants import (
    FILE_CONTENT_PATH,
    FILE_REMOTE_PATH,
    FILE_PUBLISHER_PATH,
    REPO_PATH,
)
from pulp_smash.tests.pulp3.file.api_v3.utils import gen_publisher, gen_remote
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import (
    delete_repo_version,
    get_added_content,
    get_artifact_paths,
    get_auth,
    get_content,
    get_removed_content,
    get_repo_versions,
    publish_repo,
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
        cls.remote = {}
        cls.repo = {}
        cls.content = {}

    @classmethod
    def tearDownClass(cls):
        """Destroy resources created by test methods."""
        if cls.remote:
            cls.client.delete(cls.remote['_href'])
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
        body = gen_remote()
        body['url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        self.remote.update(self.client.post(FILE_REMOTE_PATH, body))
        sync_repo(self.cfg, self.remote, self.repo)
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


class DeleteAnyRepoVersionTestCase(unittest.TestCase, utils.SmokeTest):
    """Verify that any repository version can be deleted.

    This test targets the following issues:

    * `Pulp #3219 <https://pulp.plan.io/issues/3219>`_
    * `Pulp Smash #871 <https://github.com/PulpQE/pulp-smash/issues/871>`_
    """

    def setUp(self):
        """Create class-wide variables."""
        self.cfg = config.get_config()
        self.client = api.Client(self.cfg, api.json_handler)
        self.client.request_kwargs['auth'] = get_auth()
        body = gen_remote()
        body['url'] = urljoin(FILE_LARGE_FEED_URL, 'PULP_MANIFEST')
        importer = self.client.post(FILE_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, importer['_href'])
        self.repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, self.repo['_href'])
        sync_repo(self.cfg, importer, self.repo)

    def test_01_delete_any_version(self):
        """Verify that any repository version can be deleted.

        1. Delete a version (e.g. 1) and verify doesn't affect the content of
           successive versions (e.g. 2, 3, ...).
        2. Assert that the last version can be deleted.
        3. Verify whether when the last version is deleted and then a new
           version is created, it should not have the previously deleted
           version content.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        files_content = self.client.get(FILE_CONTENT_PATH)['results']

        # This file will be used to create a new version after the last one
        # is deleted.
        last_file_content = files_content.pop()
        for file_content in files_content:
            self.client.post(
                repo['_versions_href'],
                {'add_content_units': [file_content['_href']]}
            )
        versions = get_repo_versions(repo)
        artifact = get_artifact_paths(repo, versions[0])

        # Delete first repository version.
        delete_repo_version(repo, versions[0])
        with self.assertRaises(HTTPError):
            get_content(repo, versions[0])

        # Verify that second version has content added by the first one,
        # even after the first one was deleted.
        next_artifact = get_artifact_paths(repo, versions[1])
        self.assertTrue(artifact.issubset(next_artifact))

        # Delete last repository version.
        last_artifact = get_artifact_paths(repo, versions[-1])
        delete_repo_version(repo, versions[-1])
        with self.assertRaises(HTTPError):
            get_content(repo, versions[-1])

        # Pick a random version between the second one and the antepenultimate
        # one.
        index = randint(1, len(versions) - 2)

        # Read and artifact of selected index, remove selected version, and
        # read the content of the next version.
        artifact = get_artifact_paths(repo, versions[index])
        delete_repo_version(repo, versions[index])
        with self.assertRaises(HTTPError):
            get_content(repo, versions[index])
        next_artifact = get_artifact_paths(repo, versions[index + 1])
        self.assertTrue(artifact.issubset(next_artifact))

        # Get the last but one artifact.
        last_but_one_artifact = get_artifact_paths(repo, versions[-2])

        # Create new version - using the latest present version as base.
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [last_file_content['_href']]}
        )
        versions = get_repo_versions(repo)
        last_version_artifacts = get_artifact_paths(repo, versions[-1])
        self.assertFalse(last_artifact.issubset(last_version_artifacts))
        self.assertTrue(last_but_one_artifact.issubset(last_version_artifacts))

    @selectors.skip_if(bool, 'repo', False)
    def test_02_delete_publication(self):
        """Test if delete a given repo version will delete its publication."""
        publisher = self.client.post(FILE_PUBLISHER_PATH, gen_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])
        version = get_repo_versions(self.repo)[0]
        publication = publish_repo(self.cfg, publisher, self.repo, version)
        delete_repo_version(self.repo, version)
        with self.assertRaises(HTTPError):
            self.client.get(publication['_href'])
