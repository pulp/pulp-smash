# coding=utf-8
"""Copy content between OSTree repositories with a filter."""
import random
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import OSTREE_BRANCHES, OSTREE_FEED, REPOSITORY_PATH
from pulp_smash.tests.ostree.utils import gen_distributor, gen_repo
from pulp_smash.tests.ostree.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CopyTestCase(unittest.TestCase):
    """Copy content between OSTree repositories with a filter."""

    def test_all(self):
        """Copy content between OSTree repositories with a filter..

        Verify that filters can be used to restrict which units
        are copied between repositories.

        Do the following:

        1. Create a pair of repositories, and populate the first.
        2. Randomly select a unit from the first repository, and copy
            it to the second repository.
        3. Verify that the selected unit is the only one in the second
            repository.

        """
        repos = []  # list to store data related to created repos
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        # Create the 1st repository with at least 2 content units
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED
        body['importer_config']['branches'] = OSTREE_BRANCHES
        body['distributors'].append(gen_distributor())
        repos.append(client.post(REPOSITORY_PATH, body))
        self.addCleanup(client.delete, repos[0]['_href'])

        # Sync the 1st repository
        utils.sync_repo(cfg, repos[0])
        src_unit_id = random.choice(
            utils.search_units(cfg, repos[0]))['metadata']['_id']

        # Create the 2nd repository
        body = gen_repo()
        repos.append(client.post(REPOSITORY_PATH, body))
        self.addCleanup(client.delete, repos[1]['_href'])

        # Copy random unit from the 1st repo to 2nd one.
        client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'criteria': {
                'filters': {'unit': {'_id': src_unit_id}},
                'type_ids': ['ostree'],
            },
        })

        # Search for random copied unit on 2nd repo
        dst_unit_ids = [
            unit['metadata']['_id'] for unit in
            utils.search_units(cfg, repos[1], {
                'filters': {}, 'type_ids': ['ostree']
            })
        ]

        # Assert unit from 1st repo was copied to 2nd
        self.assertEqual([src_unit_id], dst_unit_ids)
