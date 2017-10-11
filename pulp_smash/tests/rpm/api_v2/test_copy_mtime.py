# coding=utf-8
"""Test whether copy of directory will copy the ``mtime``."""
import os
import re
import time
import unittest

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM_SIGNED_URL,
    RPM_UNSIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PATH = '/var/lib/pulp/published/yum/https/repos/'


class CopyDirectoryStepTestCase(unittest.TestCase):
    """Test whether copy of directory will copy the ``mtime``."""

    def test_all(self):
        """Test whether copy of directory will copy the ``mtime``.

        This test targets the following issues:

        * `Pulp Smash #720 <https://github.com/PulpQE/pulp-smash/issues/720>`_
        * `Pulp #2783 <https://pulp.plan.io/issues/2783>`_

        Do the following:

        1. Create and sync a repository.
        2. Publish the repository with the option ``generate_sqlite``
           as True.
        3. Verify the ``mtime`` for the sqlite files.
        4. Upload a RPM package to the repository.
        5. Sync the repository again.
        6. Assert that ``mtime`` for old sqlite files remain the same.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(2783, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2783')
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo, {
            'id': repo['distributors'][0]['id'],
            'override_config': {'generate_sqlite': True},
        })
        repo = client.get(repo['_href'], params={'details': True})
        path = os.path.join(
            _PATH,
            repo['distributors'][0]['config']['relative_url'],
            'repodata'
        )
        system = cfg.get_systems('pulp cli')[0]
        sudo = () if utils.is_root(cfg, system) else ('sudo',)
        cli_client = cli.Client(cfg, cli.echo_handler)
        responses = cli_client.run(sudo + (
            'ls', '-l', '--full-time', path
        )).stdout.splitlines()
        initial_time = {
            get_time(response)
            for response in responses
            if 'sqlite' in response
        }
        time.sleep(5)
        rpm = utils.http_get(RPM_SIGNED_URL)
        utils.upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)
        utils.sync_repo(cfg, repo)
        responses = cli_client.run(sudo + (
            'ls', '-l', '--full-time', path
        )).stdout.splitlines()
        final_time = {
            get_time(response)
            for response in responses
            if 'sqlite' in response
        }
        self.assertEqual(initial_time, final_time)


def get_time(string):
    """Parse a string and return the first match XX:XX:XX.

    Where X is a digit [0-9].
    """
    return re.findall(r'\d{2}:\d{2}:\d{2}', string)[0]
