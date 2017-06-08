# coding=utf-8
"""Test re-publish repository after unassociating content.

Following steps are executed in order to test correct functionality of
repository created with valid feed.

1. Create repository foo with valid feed, run sync, add distributor to it and
   publish over http and https.
2. Pick a unit X and and assert it is accessible.
3. Remove unit X from repository foo and re-publish.
4. Assert unit X is not accessible.
"""
import random
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_SIGNED_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_unit,
)
from pulp_smash.tests.rpm.utils import check_issue_2277, check_issue_2620
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


class RepublishTestCase(unittest.TestCase):
    """Test re-publish repository after unassociating content."""

    def test_all(self):
        """Create one repository with feed, unassociate unit and re-publish.

        Following steps are executed:

        1. Create, sync and publish a repository.
        2. Pick a content unit from the repository and verify it can be
           downloaded.
        3. Remove the content unit from the repository, re-publish, and verify
           it can't be downloaded.
        """
        cfg = config.get_config()
        if check_issue_2277(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        if check_issue_2620(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')

        # Create, sync and publish a repository.
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo)

        # Pick a random content unit and verify it's accessible.
        unit = random.choice(
            utils.search_units(cfg, repo, {'type_ids': ('rpm',)})
        )
        filename = unit['metadata']['filename']
        get_unit(cfg, repo['distributors'][0], filename)

        # Remove the content unit and verify it's inaccessible.
        client.post(
            urljoin(repo['_href'], 'actions/unassociate/'),
            {'criteria': {'filters': {'unit': {'filename': filename}}}},
        )
        utils.publish_repo(cfg, repo)
        with self.assertRaises(KeyError):
            get_unit(cfg, repo['distributors'][0], filename)
