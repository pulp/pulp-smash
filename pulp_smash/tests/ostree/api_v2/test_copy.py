# coding=utf-8
"""Test copy of specific content from/to OSTree repositories."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import OSTREE_BRANCH, OSTREE_FEED, REPOSITORY_PATH,\
    OSTREE_FEED_SMALL
from pulp_smash.tests.ostree.utils import gen_distributor, gen_repo
from pulp_smash.tests.ostree.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CopyTestCase(unittest.TestCase):
    """Test copy of specific content from/to OSTree repositories."""

    def test_all(self):
        """Test copy of specific content from/to OSTree repositories.

        Verify that:

        * When doing a copy from one OSTree repo to another, just certain units
        in the repo get copied, based on what filters were supplied.
        """
        repos = []  # list to store data related to created repos
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        # Create the 1st repository with at least 2 content units
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED_SMALL
        body['importer_config']['branches'] = ['rawhide', 'stable']
        body['distributors'].append(gen_distributor())
        repo = client.post(REPOSITORY_PATH, body)
        repos.append(repo)
        self.addCleanup(client.delete, repo['_href'])

        # Sync the 1st repository
        utils.sync_repo(cfg, repo)
        first_unit_first_repo = utils.search_units(
            cfg, repos[0], {})[0]['metadata']['_id']
        second_unit_first_repo = utils.search_units(
            cfg, repos[0], {})[1]['metadata']['_id']

        # Create the 2nd repository
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED
        body['importer_config']['branches'] = [OSTREE_BRANCH]
        body['distributors'].append(gen_distributor())
        repo = client.post(REPOSITORY_PATH, body)
        repos.append(repo)
        self.addCleanup(client.delete, repo['_href'])

        # Copy 2nd unit from the 1st repo to 2nd one.
        client.post(
            urljoin(repos[1]['_href'], 'actions/associate/'), {
                'source_repo_id': repos[0]['id'],
                'criteria': {
                    'filters': {'unit': {'_id': second_unit_first_repo}},
                    'type_ids': ['ostree'],
                },
            })

        # Assert that 1st unit was not copied into 2nd repo
        criteria = {
            'filters': {'unit': {'_id': first_unit_first_repo}},
            'type_ids': ['ostree'],
        }

        len_search = len(utils.search_units(cfg, repos[1], criteria))
        with self.subTest(comment='verify 1st unit was not copied'):
            self.assertEqual(0, len_search)

        # Search the 2nd unit on the 2nd repo
        unit_second_repo = utils.search_units(cfg, repos[1], {})
        unit_second_repo = unit_second_repo[0]['metadata']['_id']

        # Assert that the 2nd unit was copied into 2nd repo
        with self.subTest(comment='verify just filtered unit was copied'):
            self.assertEqual(second_unit_first_repo, unit_second_repo)
