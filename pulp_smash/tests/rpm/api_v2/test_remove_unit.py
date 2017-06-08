# coding=utf-8
"""Tests for the `remove_missing`_ repository option.

.. _remove_missing:
    https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html
"""
import random
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM_SIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import check_issue_2277, check_issue_2620
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


class RemoveMissingTestCase(unittest.TestCase):
    """Test the `remove_missing`_ repository option.

    The test procedure is as follows:

    1. Create a repository, populate it with content, and publish it.
    2. Create several more repositories whose "feed" attribute references the
       repository created in the previous step. Sync each of these child
       repositories.
    3. Remove a content unit from the parent repository and re-publish it.
    4. Re-sync each of the child repositories.

    The child repositories are designed to test the following issues:

    * `Pulp #1621 <https://pulp.plan.io/issues/1621>`_
    * `Pulp #2503 <https://pulp.plan.io/issues/2503>`_

    .. _remove_missing:
        https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html
    """

    @classmethod
    def setUpClass(cls):
        """Initialize class-wide variables."""
        cls.cfg = config.get_config()
        cls.repos = {}  # Each inner dict has info about a repository.
        if check_issue_2277(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        if check_issue_2620(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')

    @classmethod
    def tearDownClass(cls):
        """Delete all resources named by ``resources``."""
        client = api.Client(cls.cfg)
        for repo in cls.repos.values():
            client.delete(repo['_href'])
        client.delete(ORPHANS_PATH)

    def test_01_create_root_repo(self):
        """Create, sync and publish a repository.

        The repositories created in later steps sync from this one.
        """
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        self.repos['root'] = client.post(REPOSITORY_PATH, body)
        self.repos['root'] = _get_details(self.cfg, self.repos['root'])
        utils.sync_repo(self.cfg, self.repos['root'])
        utils.publish_repo(self.cfg, self.repos['root'])

    def test_02_create_immediate_child(self):
        """Create a child repository with the "immediate" download policy.

        Sync the child repository, and verify it has the same contents as the
        root repository.
        """
        # We disable SSL validation for a practical reason: each HTTPS feed
        # must have a certificate to work, which is burdensome to do here.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = urljoin(
            self.cfg.base_url,
            _PUBLISH_DIR +
            self.repos['root']['distributors'][0]['config']['relative_url'],
        )
        body['importer_config']['remove_missing'] = True
        body['importer_config']['ssl_validation'] = False
        self.repos['immediate'] = client.post(REPOSITORY_PATH, body)
        self.repos['immediate'] = (
            _get_details(self.cfg, self.repos['immediate'])
        )
        utils.sync_repo(self.cfg, self.repos['immediate'])

        # Verify the two repositories have the same contents.
        root_ids = _get_rpm_ids(_get_rpms(self.cfg, self.repos['root']))
        immediate_ids = _get_rpm_ids(
            _get_rpms(self.cfg, self.repos['immediate'])
        )
        self.assertEqual(root_ids, immediate_ids)

    def test_02_create_on_demand_child(self):
        """Create a child repository with the "on_demand" download policy.

        Also, let the repository's "remove_missing" option be true. Then, sync
        the child repository, and verify it has the same contents as the root
        repository.
        """
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = urljoin(
            self.cfg.base_url,
            _PUBLISH_DIR +
            self.repos['root']['distributors'][0]['config']['relative_url'],
        )
        body['importer_config']['download_policy'] = 'on_demand'
        body['importer_config']['remove_missing'] = True
        body['importer_config']['ssl_validation'] = False
        self.repos['on demand'] = client.post(REPOSITORY_PATH, body)
        self.repos['on demand'] = (
            _get_details(self.cfg, self.repos['on demand'])
        )
        utils.sync_repo(self.cfg, self.repos['on demand'])

        # Verify the two repositories have the same contents.
        root_ids = _get_rpm_ids(_get_rpms(self.cfg, self.repos['root']))
        on_demand_ids = _get_rpm_ids(
            _get_rpms(self.cfg, self.repos['on demand'])
        )
        self.assertEqual(root_ids, on_demand_ids)

    def test_03_update_root_repo(self):
        """Remove a content unit from the root repository and republish it."""
        unit = random.choice(_get_rpms(self.cfg, self.repos['root']))
        criteria = {
            'filters': {'unit': {'name': unit['metadata']['name']}},
            'type_ids': [unit['unit_type_id']],
        }
        api.Client(self.cfg).post(
            urljoin(self.repos['root']['_href'], 'actions/unassociate/'),
            {'criteria': criteria}
        ).json()
        utils.publish_repo(self.cfg, self.repos['root'])

        # Verify the removed unit cannot be found via a search.
        units = utils.search_units(self.cfg, self.repos['root'], criteria)
        self.assertEqual(len(units), 0, units)

    def test_04_sync_immediate_child(self):
        """Sync the "immediate" repository.

        Verify it has the same contents as the root repository.
        """
        utils.sync_repo(self.cfg, self.repos['immediate'])
        root_ids = _get_rpm_ids(_get_rpms(self.cfg, self.repos['root']))
        immediate_ids = _get_rpm_ids(
            _get_rpms(self.cfg, self.repos['immediate'])
        )
        self.assertEqual(root_ids, immediate_ids)

    def test_04_sync_on_demand_child(self):
        """Sync the "on demand" repository.

        Verify it has the same contents as the root repository.
        """
        utils.sync_repo(self.cfg, self.repos['on demand'])
        root_ids = _get_rpm_ids(_get_rpms(self.cfg, self.repos['root']))
        on_demand_ids = _get_rpm_ids(
            _get_rpms(self.cfg, self.repos['on demand'])
        )
        self.assertEqual(root_ids, on_demand_ids)


def _get_rpms(cfg, repo):
    """Return RPM content units in the given repository."""
    return utils.search_units(cfg, repo, {'type_ids': ('rpm',)})


def _get_rpm_ids(search_body):
    """Get RPM unit IDs from repository search results. Return as a set."""
    return {
        unit['unit_id'] for unit in search_body
        if unit['unit_type_id'] == 'rpm'
    }


def _get_details(cfg, repo):
    """Get detailed information about the given repository."""
    return api.Client(cfg).get(repo['_href'], params={'details': True}).json()
