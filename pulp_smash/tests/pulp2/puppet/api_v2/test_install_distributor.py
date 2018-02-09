# coding=utf-8
"""Tests for puppet_install_distributor.

For more information check `puppet_install_distributor`_

.. _puppet_install_distributor:
    http://docs.pulpproject.org/plugins/pulp_puppet/tech-reference/plugin_conf.html?#install-distributor
"""
from requests.exceptions import HTTPError

from pulp_smash import api, cli, utils, selectors
from pulp_smash.constants import PUPPET_MODULE_1, PUPPET_MODULE_URL_1
from pulp_smash.tests.pulp2.constants import REPOSITORY_PATH
from pulp_smash.tests.pulp2.puppet.api_v2.utils import (
    gen_install_distributor,
    gen_repo,
)
from pulp_smash.tests.pulp2.puppet.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class InstallDistributorTestCase(utils.BaseAPITestCase):
    """Test Puppet install distributor."""

    def test_all(self):
        """Test puppet_install_distributor.

        Do the following:

        1. Create a puppet repository with a puppet_install_distributor
        2. Upload a puppet module
        3. Publish the repository
        4. Check if the puppet_install_distributor config was properly used
        """
        if (selectors.bug_is_untestable(3314, self.cfg.pulp_version) and
                utils.os_is_f27(self.cfg)):
            self.skipTest('https://pulp.plan.io/issues/3314')
        cli_client = cli.Client(self.cfg)
        sudo = () if utils.is_root(self.cfg) else ('sudo',)

        # Create a directory and make sure Pulp can write to it.
        install_path = cli_client.run(('mktemp', '--directory')).stdout.strip()
        self.addCleanup(cli_client.run, sudo + ('rm', '-rf', install_path))
        cli_client.run(sudo + ('chown', 'apache:apache', install_path))
        cli_client.run(sudo + ('chcon', '-t', 'puppet_etc_t', install_path))

        # Make sure the pulp_manage_puppet boolean is enabled
        cli_client.run(sudo + ('setsebool', 'pulp_manage_puppet', 'on'))
        self.addCleanup(cli_client.run, sudo + (
            'setsebool', 'pulp_manage_puppet', 'off'))

        # Create and populate a Puppet repository.
        distributor = gen_install_distributor()
        distributor['distributor_config']['install_path'] = install_path
        body = gen_repo()
        body['distributors'] = [distributor]
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        unit = utils.http_get(PUPPET_MODULE_URL_1)
        utils.upload_import_unit(
            self.cfg, unit, {'unit_type_id': 'puppet_module'}, repo)

        # Publish, and verify the module is present. (Dir has 700 permissions.)
        utils.publish_repo(self.cfg, repo)
        proc = cli_client.run(sudo + (
            'runuser', '--shell', '/bin/sh', '--command',
            'ls -1 {}'.format(install_path), '-', 'apache'
        ))
        self.assertIn(PUPPET_MODULE_1['name'], proc.stdout.split('\n'), proc)


class InstallDistributorThrowsOnErrorTestCase(utils.BaseAPITestCase):
    """Test Puppet install distributor."""

    def test_all(self):
        """Creating a repo with an invalid distributor should throw an error.

        This test targets `Pulp #1237 <https://pulp.plan.io/issues/1237>`_.
        Do the following:

        1. Create a puppet repo
        2. Make an API call to create a distributor WITHOUT non-optional
            install_path
        3. Assert that an error is thrown
        4. Assert that no repo is created
        """
        if selectors.bug_is_untestable(1237, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1237')
        distributor = gen_install_distributor()
        distributor['distributor_config']['install_path'] = ''
        body = gen_repo()
        body['distributors'] = [distributor]
        client = api.Client(self.cfg, api.json_handler)
        with self.assertRaises(HTTPError):
            repo = client.post(REPOSITORY_PATH, body)
            self.addCleanup(client.delete, repo['_href'])
