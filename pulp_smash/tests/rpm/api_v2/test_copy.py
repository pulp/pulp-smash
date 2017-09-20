# coding=utf-8
"""Tests for copying RPM units between repositories."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_UPDATED_INFO_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CopyErrataRecursiveTestCase(unittest.TestCase):
    """Test that recursive copy of erratas copies RPM packages."""

    def test_all(self):
        """Test that recursive copy of erratas copies RPM packages.

        This test targets the following issues:

        * `Pulp Smash #769 <https://github.com/PulpQE/pulp-smash/issues/769>`_
        * `Pulp #3004 <https://pulp.plan.io/issues/3004>`_

        Do the following:

        1. Create and sync a repository with errata, and RPM packages.
        2. Create second repository.
        3. Copy units from from first repository to second repository
           using ``recursive`` as true, and filter  ``type_id`` as
           ``erratum``.
        4. Assert that RPM packages were copied.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(3004, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/3004')

        repos = []
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UPDATED_INFO_FEED_URL
        body['distributors'] = [gen_distributor()]
        repos.append(client.post(REPOSITORY_PATH, body))
        self.addCleanup(client.delete, repos[0]['_href'])
        utils.sync_repo(cfg, repos[0])

        # Create a second repository.
        repos.append(client.post(REPOSITORY_PATH, gen_repo()))
        self.addCleanup(client.delete, repos[1]['_href'])

        # Copy data to second repository.
        client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {'recursive': True},
            'criteria': {'filters': {}, 'type_ids': ['erratum']},
        })

        # Assert that RPM packages were copied.
        units = utils.search_units(cfg, repos[1], {'type_ids': ['rpm']})
        self.assertGreater(len(units), 0)
