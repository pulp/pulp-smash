# coding=utf-8
"""Tests that publish OSTree repositories."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import OSTREE_BRANCH, OSTREE_FEED, REPOSITORY_PATH
from pulp_smash.tests.ostree.utils import gen_distributor, gen_repo
from pulp_smash.tests.ostree.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class PublishTestCase(unittest.TestCase):
    """Create, sync and publish an OSTree repository."""

    def test_all(self):
        """Create, sync and publish an OSTree repository.

        Verify that:

        * The distributor's ``last_publish`` attribute is ``None`` after the
          sync. This demonstrates that ``auto_publish`` correctly defaults to
          ``False``.
        * The distributor's ``last_publish`` attribute is not ``None`` after
          the publish.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        # Create a repository.
        body = gen_repo()
        body['importer_config']['feed'] = OSTREE_FEED
        body['importer_config']['branches'] = [OSTREE_BRANCH]
        body['distributors'].append(gen_distributor())
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])

        # Sync the repository.
        utils.sync_repo(cfg, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        with self.subTest(comment='verify last_publish after sync'):
            self.assertIsNone(repo['distributors'][0]['last_publish'])

        # Publish the repository.
        client.post(urljoin(repo['_href'], 'actions/publish/'), {
            'id': repo['distributors'][0]['id'],
        })
        repo = client.get(repo['_href'], params={'details': True})
        with self.subTest(comment='verify last_publish after publish'):
            self.assertIsNotNone(repo['distributors'][0]['last_publish'])
