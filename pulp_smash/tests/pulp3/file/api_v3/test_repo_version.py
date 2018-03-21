# coding=utf-8
"""Tests related to repository version."""
import unittest
from random import choice
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import FILE_FEED_COUNT, FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import (
    FILE_CONTENT_PATH,
    FILE_IMPORTER_PATH,
    REPO_PATH,
)
from pulp_smash.tests.pulp3.file.api_v3.utils import gen_importer
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import (
    get_auth,
    get_latest_repo_version,
    read_repo_added_content,
    read_repo_content,
    read_repo_removed_content,
    sync_repo,
)


class AddingRemovingUnitsTestCase(unittest.TestCase, utils.SmokeTest):
    """Create new repo version adding or removing content."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        Sync a repository.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        body = gen_importer()
        body['feed_url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        cls.importer = cls.client.post(FILE_IMPORTER_PATH, body)
        cls.repo = cls.client.post(REPO_PATH, gen_repo())
        sync_repo(cls.cfg, cls.importer, cls.repo)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variables."""
        cls.client.delete(cls.importer['_href'])
        cls.client.delete(cls.repo['_href'])

    def test_01_create_repo_version(self):
        """Create a new repo version adding or removing content.

        This test explores the design choice stated in `Pulp #3234`_ that
        create a new repository version by adding or removing content to the
        latest version of the repository.

        .. _Pulp #3234: https://pulp.plan.io/issues/3234

        Do the following:

        1. Create a repository.
        2. Use ``add_content_units`` to pass an url for a unit to be added
           to the repository.
        3. Assert that the repository version has changed.
        4. Assert that there is just one content unit in the repository.
        5. Remove the just added unit from the repository using the
           ``remove_content_units``, and assert that the repository version
           has changed.
        6. Assert that there are no content units present in the repository.
        """
        # Create repository.
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        repo_versions = []
        repo_versions.append(get_latest_repo_version(repo))

        # Add content unit to the second repository.
        file_content = self.client.get(FILE_CONTENT_PATH)['results']
        content_href = choice(file_content)['_href']
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [content_href]}
        )
        repo_versions.append(get_latest_repo_version(repo))
        self.assertNotEqual(repo_versions[0], repo_versions[1])
        self.assertEqual(len(read_repo_content(repo)['results']), 1)
        self.assertEqual(
            content_href,
            read_repo_content(repo)['results'][0]['_href']
        )

        # Remove content unit from the second repository.
        self.client.post(
            repo['_versions_href'],
            {'remove_content_units': [content_href]}
        )
        repo_versions.append(get_latest_repo_version(repo))
        self.assertNotEqual(repo_versions[1], repo_versions[2])
        self.assertEqual(len(read_repo_content(repo)['results']), 0)

    def test_02_view_content(self):
        """Test whether a user can view content for a repository version.

        This test targets the following issues:

        * `Pulp #3059 <https://pulp.plan.io/issues/3059>`_
        * `Pulp Smash #878 <https://github.com/PulpQE/pulp-smash/issues/878>`_

        Do the following:

        1. Assert that ``content_summary`` has the correct number of files
           according to the sync ``feed_url``.
        2. Assert that the content present on the last version of repository
           is equal to the content that was added to the the last version.
           Inspect ``/added_content/`` and ``/content/`` endpoints to
           achieve this.
        3. Remove a content unit from the repository, and assert that endpoint
           ``removed_content`` represents this change.
        """
        versions_href = self.client.get(self.repo['_href'])['_versions_href']
        detail_view = self.client.get(versions_href)
        content_summary = detail_view['results'][0]['content_summary']
        self.assertEqual(int(content_summary['file']), FILE_FEED_COUNT)
        repo_content = read_repo_content(self.repo)
        added_content = read_repo_added_content(self.repo)
        self.assertListEqual(
            repo_content['results'],
            added_content['results']
        )
        content_href = choice(repo_content['results'])['_href']
        self.client.post(
            self.repo['_versions_href'],
            {'remove_content_units': [content_href]}
        )
        removed_content = read_repo_removed_content(self.repo)
        self.assertEqual(content_href, removed_content['results'][0]['_href'])
