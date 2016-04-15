# coding=utf-8
"""Test the removal of rpm orphans.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.
"""
from __future__ import unicode_literals

from pulp_smash import api, utils
from pulp_smash.constants import ORPHANS_PATH, REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _count_orphans(client):
    """Count the number of orphans."""
    orphan_dict = client.get(ORPHANS_PATH)
    total_orphans = 0
    for _, data in orphan_dict.items():
        total_orphans += data.get('count') or 0
    return total_orphans


class OrphanRemoveAllTestCase(utils.BaseAPITestCase):
    """Establish that orphan removal does a full cleanup."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repo, sync it, delete the repo, remove orphans."""
        super(OrphanRemoveAllTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        utils.sync_repo(cls.cfg, repo['_href'])

        cls.num_orphans_pre_repo_del = _count_orphans(client)
        client.delete(repo['_href'])
        cls.num_orphans_post_repo_del = _count_orphans(client)
        client.delete(ORPHANS_PATH)
        cls.num_orphans_after_rm = _count_orphans(client)

    def test_orphans_created(self):
        """Ensure that orphans were created by deleting the repository.

        Failure of this test indicates that other repositories may still exist
        in the db that have associated the units, thus not creating orphans
        as expected.
        """
        self.assertLessEqual(
            self.num_orphans_pre_repo_del,
            self.num_orphans_post_repo_del,
        )
        self.assertGreaterEqual(self.num_orphans_post_repo_del, 39)

    def test_orphans_removed(self):
        """Ensure that all orphans were removed."""
        self.assertEqual(self.num_orphans_after_rm, 0)
