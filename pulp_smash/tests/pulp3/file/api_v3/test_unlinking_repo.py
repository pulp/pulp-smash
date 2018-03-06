# coding=utf-8
"""Tests that perform action over importers and publishers."""

import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import (
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
    publish_repo,
    read_repo_content,
    sync_repo,
)


class ImportersPublishersTestCase(unittest.TestCase, utils.SmokeTest):
    """Verify publisher and importer can be used with different repos."""

    def test_all(self):
        """Verify publisher and importer can be used with different repos.

        This test explores the design choice stated in `Pulp #3341`_ that
        remove the FK from publishers and importers to repository.
        Allowing importers and publishers to be used with different
        repositories.

        .. _Pulp #3341: https://pulp.plan.io/issues/3341

        Do the following:

        1. Create an importer, and a publisher.
        2. Create 2 repositories.
        3. Sync both repositories using the same importer.
        4. Assert that the two repositories have the same contents.
        5. Publish both repositories using the same publisher.
        6. Assert that each generated publication has the same publisher, but
           are associated with different repositories.
        """
        # Create an importer and publisher.
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        body = gen_importer()
        body['feed_url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        importer = client.post(FILE_IMPORTER_PATH, body)
        self.addCleanup(client.delete, importer['_href'])
        publisher = client.post(FILE_PUBLISHER_PATH, gen_publisher())
        self.addCleanup(client.delete, publisher['_href'])

        # Create and sync repos.
        repos = []
        for _ in range(2):
            repos.append(client.post(REPO_PATH, gen_repo()))
            self.addCleanup(client.delete, repos[-1]['_href'])
            sync_repo(cfg, importer, repos[-1])

        # Compare contents of repositories.
        contents = []
        for repo in repos:
            contents.append(read_repo_content(repo)['results'])
        self.assertEqual(
            {content['_href'] for content in contents[0]},
            {content['_href'] for content in contents[1]},
        )

        # Publish repositories.
        publications = []
        for repo in repos:
            publications.append(publish_repo(cfg, publisher, repo))
            if selectors.bug_is_testable(3354, cfg.pulp_version):
                self.addCleanup(client.delete, publications[-1]['_href'])
        self.assertEqual(
            publications[0]['publisher'],
            publications[1]['publisher']
        )
        self.assertNotEqual(
            publications[0]['repository_version'],
            publications[1]['repository_version']
        )
