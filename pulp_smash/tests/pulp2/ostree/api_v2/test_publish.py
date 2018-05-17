# coding=utf-8
"""Tests that publish OSTree repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.constants import OSTREE_BRANCHES, OSTREE_FEED
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import publish_repo, sync_repo
from pulp_smash.tests.pulp2.ostree.utils import gen_distributor, gen_repo
from pulp_smash.tests.pulp2.ostree.utils import set_up_module as setUpModule  # pylint:disable=unused-import


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
        body['importer_config']['branches'] = OSTREE_BRANCHES
        body['distributors'].append(gen_distributor())
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])

        # Sync the repository.
        sync_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        with self.subTest(comment='verify last_publish after sync'):
            self.assertIsNone(repo['distributors'][0]['last_publish'])

        # Publish the repository.
        publish_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        with self.subTest(comment='verify last_publish after publish'):
            self.assertIsNotNone(repo['distributors'][0]['last_publish'])
