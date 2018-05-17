# coding=utf-8
"""Tests that copy content between OSTree repositories."""
import random
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.constants import OSTREE_BRANCHES, OSTREE_FEED
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import search_units, sync_repo
from pulp_smash.tests.pulp2.ostree.utils import gen_distributor, gen_repo
from pulp_smash.tests.pulp2.ostree.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class FilterTestCase(unittest.TestCase):
    """Copy content between OSTree repositories with a filter."""

    def test_all(self):
        """Copy content between OSTree repositories with a filter.

        Do the following:

        1. Create a pair of repositories, and populate the first.
        2. Randomly select a unit from the first repository, and copy
           it to the second repository.
        3. Verify that the selected unit is the only one in the second
           repository.
        """
        repos = []
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        # Create and populate a source repository.
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED
        body['importer_config']['branches'] = OSTREE_BRANCHES
        body['distributors'] = [gen_distributor()]
        repos.append(client.post(REPOSITORY_PATH, body))
        self.addCleanup(client.delete, repos[0]['_href'])
        sync_repo(cfg, repos[0])

        # Create a destination repository.
        repos.append(client.post(REPOSITORY_PATH, gen_repo()))
        self.addCleanup(client.delete, repos[1]['_href'])

        # Copy a random unit between the repos, and verify the result.
        src_unit_id = random.choice(
            search_units(cfg, repos[0])
        )['metadata']['_id']
        client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'criteria': {
                'filters': {'unit': {'_id': src_unit_id}},
                'type_ids': ['ostree'],
            },
        })
        dst_unit_ids = [
            unit['metadata']['_id'] for unit in
            search_units(cfg, repos[1], {'type_ids': ['ostree']})
        ]
        self.assertEqual([src_unit_id], dst_unit_ids)
