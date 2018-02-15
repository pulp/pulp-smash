# coding=utf-8
"""Tests related to repository version."""
import unittest
from random import choice
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import (
    FILE_CONTENT_PATH,
    FILE_IMPORTER_PATH,
    FILE_PUBLISHER_PATH,
    REPO_PATH,
)
from pulp_smash.tests.pulp3.file.api_v3.utils import (
    gen_importer,
    gen_publisher,
)
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import (
    get_auth,
    get_latest_repo_version,
    read_repo_content,
    sync_repo,
)


class AddingRemovingUnitsTestCase(unittest.TestCase, utils.SmokeTest):
    """Create new repo version adding or removing content."""

    def test_all(self):
        """Create a new repo version adding or removing content.

        This test explores the design choice stated in `Pulp #3234`_ that
        create a new repository version by adding or removing content to the
        latest version of the repository.

        .. _Pulp #3234: https://pulp.plan.io/issues/3234

        Do the following:

        1. Create and sync a repository.
        2. Create a second repository.
        3. Use ``add_content_units`` to pass an url for a unit to be added
           to second repository.
        4. Assert that the repository version has changed for the second
           repository.
        5. Assert that there is just one content unit in the second repository.
        6. Remove the just added unit from the second repository using the
           ``remove_content_units``, and assert that the repository version has
           changed.
        7. Assert that there are no content units present in the second
           repository.
        """
        # Add content to Pulp.
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        body = gen_importer()
        body['feed_url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        importer = client.post(FILE_IMPORTER_PATH, body)
        self.addCleanup(client.delete, importer['_href'])
        publisher = client.post(FILE_PUBLISHER_PATH, gen_publisher())
        self.addCleanup(client.delete, publisher['_href'])
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        sync_repo(cfg, importer, repo)

        # Create second repository.
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        repo_versions = []
        repo_versions.append(get_latest_repo_version(repo))

        # Add content unit to the second repository.
        file_content = client.get(FILE_CONTENT_PATH)['results']
        content_href = choice(file_content)['_href']
        client.post(
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
        client.post(
            repo['_versions_href'],
            {'remove_content_units': [content_href]}
        )
        repo_versions.append(get_latest_repo_version(repo))
        self.assertNotEqual(repo_versions[1], repo_versions[2])
        self.assertEqual(len(read_repo_content(repo)['results']), 0)
