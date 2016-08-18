# coding=utf-8
"""Basic test for rpm rsync distributor.

This test do basic publish operation in rsync distributor with rpm repository
which was previously published in yum_distributor

"""
from __future__ import unicode_literals

import unittest2
from packaging.version import Version

from pulp_smash import api, config, utils, cli, selectors, exceptions
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module


_REPO = None


def get_remote_repo_packages(yum_distributor, rsync_distributor):
    """Return 'ls' output of packages directory of repo in remote server."""
    cli_client = cli.Client(config.get_config())
    repo_relative = yum_distributor['config']['relative_url']
    remote_root = rsync_distributor['config']['remote']['root']
    ret = cli_client.run(['ls', '%s/%s' % (remote_root, repo_relative)])
    if ret.returncode:
        return (False, ret.stderr)
    else:
        return (True, ret.stdout)


def gen_rsync_distributor():
    """Return a dict for use in creating a rsync distributor."""
    return {
        'auto_publish': False,
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'rpm_rsync_distributor',
        'distributor_config': {
            'remote': {
                'auth_type': 'password',
                'key_path': '/etc/rsync_key',
                'login': 'cdn_user',
                'ssh_login': 'cdn_user',
                'ssh_password': 'cdn_user',
                'root': '/home/cdn_user/cdn/',
                'host': 'dev'},
            'http': True,
            'https': False,
            'handler_type': 'rsync'
        },
    }


def setUpModule():  # pylint:disable=invalid-name
    """Prepare remote environemnt for rsync distributor.

    1. Add cdn_user
    2. Setup password for cdn_user
    3. Setup ssh rsa-key and key authentication for ssh

    Skip all tests if rsync_distributor features is not testable in pulp.
    """
    set_up_module()
    cfg = config.get_config()
    if cfg.version < Version('2.9'):
        raise unittest2.SkipTest('This module requires Pulp 2.9 or greater.')
    if selectors.bug_is_untestable(1759, cfg.version):
        raise unittest2.SkipTest(
            'https://pulp.plan.io/issues/1759 is not testable'
        )

    cli_client = cli.Client(config.get_config(), cli.echo_handler)
    cli_client.run(['adduser', 'cdn_user'])
    cmd = cli_client.machine['echo']['cdn_user']
    cmd |= cli_client.machine['passwd']['cdn_user']['--stdin']
    cmd.run()
    cli_client.run(['ssh-keygen', '-f', '/etc/rsync_key',
                    '-t', 'rsa', '-N '' -P '''])
    cli_client.run('chown apache /etc/rsync_key'.split())
    cli_client.run('sudo -u cdn_user mkdir -p /home/cdn_user/.ssh/'.split())
    cli_client.run(('sudo -u cdn_user cp /etc/rsync_key.pub ' +
                    '/home/cdn_user/.ssh/authorized_keys').split())
    cli_client.run('chown apache /home/cdn_user/.ssh/authorized_keys'.split())


def tearDownModule():  # pylint:disable=invalid-name
    """Delete the repository created by :meth:`setUpModule`."""
    cli_client = cli.Client(config.get_config())
    cli_client.run('userdel cdn_user'.split())


def get_repomd_xml_path(distributor_rel_url):
    """Construct the path to a repository's ``repomd.xml`` file.

    :param distributor_rel_url: A distributor's ``relative_url`` option.
    :returns: An string path to a ``repomd.xml`` file.
    """
    return urljoin(
        urljoin('/pulp/repos/', distributor_rel_url),
        'repodata/repomd.xml',
    )


class TestRsyncDistributor(utils.BaseAPITestCase):
    """Basic test for rpm rsync distributor.

    Test sequence:
    1. Create rpm repo with feed
    2. Sync repo
    4. Associate yum distributor with repository
    4. Associate rsync distributor with repository
    3. Get list of packages in the repository
    4. Publish in yum distributor
    5. Publish in rsync distributor

    T1. Test if all synced packages are available in remote content location
        Test if all synced packages are available in repo destination
        repository
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository with a distributor, and populate it.

        Associate yum and rsync distributor to repository and publish
        repository in those.
        In addition, create several variables for use by the test methods.
        """
        super(TestRsyncDistributor, cls).setUpClass()
        cls.responses = {}

        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo_href = client.post(REPOSITORY_PATH, body)['_href']
        cls.resources.add(repo_href)  # mark for deletion
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo_href)
        rsync_dist = gen_rsync_distributor()
        cls.yum_distributor = client.post(urljoin(repo_href, 'distributors/'),
                                          gen_distributor())

        # Get contents of repository
        cls.synced_units = client.post(
            urljoin(repo_href, 'search/units/'),
            {'criteria': {}},
        )

        rsync_dist_conf = rsync_dist['distributor_config']
        rsync_dist_conf['predistributor_id'] = cls.yum_distributor['id']
        cls.rsync_distributor = client.post(urljoin(repo_href,
                                                    'distributors/'),
                                            rsync_dist)

        cls.responses['rpm publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': cls.yum_distributor['id']},
        )

        cls.responses['rsync publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': cls.rsync_distributor['id']},
        )

    def test_synced_data(self):
        """"Test if all content is correctly synced to remote directory.

        Test if all synced packages are available in remote content
        location Test if all synced packages are available in repo
        destination repository.
        """
        cli_client = cli.Client(config.get_config())
        remote_root = self.rsync_distributor['config']['remote']['root']
        db_rpm_units = []
        for unit in self.synced_units:
            if unit['metadata']['_content_type_id'] != 'rpm':
                continue
            db_rpm_units.append(unit)
            storage_path = unit['metadata']['_storage_path']
            rel_unit_path = storage_path.replace('/var/lib/pulp/content', '')
            ret = cli_client.run(['stat', '%s%s/%s' % (remote_root,
                                                       'content/origin',
                                                       rel_unit_path)])
            self.assertFalse(ret.returncode)

        (success, ret) = get_remote_repo_packages(self.yum_distributor,
                                                  self.rsync_distributor)
        self.assertTrue(success, ret)
        repo_packages = set(ret.split('\n'))
        db_packages = set([unit['metadata']['filename']
                           for unit in db_rpm_units])
        self.assertEqual(db_packages - repo_packages, set())


class TestRsyncDistributorConfiguration(utils.BaseAPITestCase):
    """Basic rsync distributor configuration validation.

    Test sequence:
    1. Create rpm repo with feed

    T1. test ssh_login and ssh_password is required if authtype is password
    T2. test key_path is required if authtype is publickey
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        super(TestRsyncDistributorConfiguration, cls).setUpClass()
        cls.responses = {}
        cls.distributors = {}

        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        cls.repo_href = client.post(REPOSITORY_PATH, body)['_href']
        cls.resources.add(cls.repo_href)  # mark for deletion

    def test_password_auth(self):
        """Assert ssh_key and ssh_login is required for password auth type."""
        rsync_dist_conf = gen_rsync_distributor()
        rsync_dist_conf['distributor_config']['remote'].pop('ssh_login')

        client = api.Client(self.cfg, api.echo_handler)
        with self.assertRaises(exceptions.TaskReportError):
            client.post(urljoin(self.repo_href, 'distributors/'),
                        rsync_dist_conf)

        rsync_dist_conf['distributor_config']['remote']['ssh_login'] = 'foo'
        rsync_dist_conf['distributor_config']['remote'].pop('ssh_password')
        client = api.Client(self.cfg, api.echo_handler)
        with self.assertRaises(exceptions.TaskReportError):
            client.post(urljoin(self.repo_href, 'distributors/'),
                        rsync_dist_conf)

    def test_publickey_auth(self):
        """Assert key_path is required for password auth type."""
        rsync_dist_conf = gen_rsync_distributor()
        rsync_dist_conf['distributor_config']['remote'].pop('key_path')

        client = api.Client(self.cfg, api.echo_handler)
        with self.assertRaises(exceptions.TaskReportError):
            client.post(urljoin(self.repo_href, 'distributors/'),
                        rsync_dist_conf)
