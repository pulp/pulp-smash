# coding=utf-8
"""Tests that publish file plugin repositories."""
import unittest
from random import choice
from urllib.parse import urljoin

from requests.exceptions import HTTPError

from pulp_smash import api, config, utils
from pulp_smash.constants import FILE_FEED_URL
from pulp_smash.tests.pulp3.constants import (
    FILE_CONTENT_PATH,
    FILE_REMOTE_PATH,
    FILE_PUBLISHER_PATH,
    REPO_PATH,
)
from pulp_smash.tests.pulp3.file.api_v3.utils import (
    gen_remote,
    gen_publisher,
)
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import (
    get_auth,
    get_repo_versions,
    publish_repo,
    sync_repo,
)


class PublishAnyRepoVersionTestCase(unittest.TestCase, utils.SmokeTest):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/PulpQE/pulp-smash/issues/897>`_
    """

    def test_all(self):
        """Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest
           ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        body = gen_remote()
        body['url'] = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
        remote = client.post(FILE_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        sync_repo(cfg, remote, repo)
        publisher = client.post(FILE_PUBLISHER_PATH, gen_publisher())
        self.addCleanup(client.delete, publisher['_href'])

        # Step 1
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        for file_content in client.get(FILE_CONTENT_PATH)['results']:
            client.post(
                repo['_versions_href'],
                {'add_content_units': [file_content['_href']]}
            )
        versions = get_repo_versions(repo)
        non_latest = choice(versions[:-1])

        # Step 2
        publication = publish_repo(cfg, publisher, repo)

        # Step 3
        self.assertEqual(publication['repository_version'], versions[-1])

        # Step 4
        publication = publish_repo(cfg, publisher, repo, non_latest)

        # Step 5
        self.assertEqual(publication['repository_version'], non_latest)

        # Step 6
        with self.assertRaises(HTTPError):
            body = {'repository': repo['_href'],
                    'repository_version': non_latest}
            client.post(urljoin(publisher['_href'], 'publish/'), body)
