# coding=utf-8
"""Test cases that copy content units."""
import os
import time
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    RPM_SIGNED_URL,
    RPM_UNSIGNED_FEED_URL,
    RPM_UPDATED_INFO_FEED_URL,
)
from pulp_smash.tests.pulp2.constants import REPOSITORY_PATH
from pulp_smash.tests.pulp2.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PATH = '/var/lib/pulp/published/yum/https/repos/'


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
        if selectors.bug_is_untestable(3004, cfg.pulp_version):
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


class MtimeTestCase(unittest.TestCase):
    """Test whether copied files retain their original mtime."""

    def test_all(self):
        """Test whether copied files retain their original mtime.

        This test targets the following issues:

        * `Pulp #2783 <https://pulp.plan.io/issues/2783>`_
        * `Pulp Smash #720 <https://github.com/PulpQE/pulp-smash/issues/720>`_

        Do the following:

        1. Create, sync and publish a repository, with ``generate_sqlite`` set
           to true.
        2. Get the ``mtime`` of the sqlite files.
        3. Upload an RPM package into the repository, and sync the repository.
        4. Get the ``mtime`` of the sqlite files again. Verify that the mtimes
           are the same.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(2783, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2783')

        # Create, sync and publish a repository.
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        body['distributors'][0]['distributor_config']['generate_sqlite'] = True
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo)

        # Get the mtime of the sqlite files.
        cli_client = cli.Client(cfg, cli.echo_handler)
        cmd = '' if utils.is_root(cfg) else 'sudo '
        cmd += "bash -c \"stat --format %Y '{}'/*\"".format(os.path.join(
            _PATH,
            repo['distributors'][0]['config']['relative_url'],
            'repodata',
        ))
        mtimes_pre = (
            cli_client.machine.session().run(cmd)[1].strip().split().sort()
        )

        # Upload to the repo, and sync it.
        rpm = utils.http_get(RPM_SIGNED_URL)
        utils.upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)
        utils.sync_repo(cfg, repo)

        # Get the mtime of the sqlite files again.
        time.sleep(1)
        mtimes_post = (
            cli_client.machine.session().run(cmd)[1].strip().split().sort()
        )
        self.assertEqual(mtimes_pre, mtimes_post)
