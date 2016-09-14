# coding=utf-8
"""Test the functionality of the RPM rsync distributor.

The RPM rsync distributor lets one publish content units to a directory via
rsync+ssh. A typical usage of the RPM rsync distributor is as follows:

1. Create RPM repository with yum and RPM rsync distributors.
2. Upload some content units to the repository.
3. Publish the repository with the yum distributor.
4. Publish the repository with the RPM rsync distributor.

The RPM rsync distributor may not be used by itself. One cannot create an RPM
repository with just an RPM rsync distributor; and one cannot publish a
repository with the RPM rsync distributor without first publishing with a yum
distributor.

For more information on the RPM rsync distributor, see `Pulp #1759`_.

.. _Pulp #1759: https://pulp.plan.io/issues/1759
"""
import os
import unittest
from urllib.parse import urljoin, urlparse

from requests.exceptions import HTTPError

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM_FEED_COUNT,
    RPM_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    DisableSELinuxMixin,
    gen_distributor,
    gen_repo,
)
from pulp_smash.tests.rpm.utils import set_up_module


def _split_path(path):
    """Split a filesystem path into all of its component pieces."""
    head, tail = os.path.split(path)
    if head == '':
        return (tail,)
    else:
        return _split_path(head) + (tail,)


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip the tests in this module.

    Skip the tests in this module if:

    * The RPM plugin is not installed on the target Pulp server.
    * `Pulp #1759`_ is not implemented on the target Pulp server.

    .. _Pulp #1759: https://pulp.plan.io/issues/1759
    """
    set_up_module()
    if selectors.bug_is_untestable(1759, config.get_config().version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/1759')


def tearDownModule():  # pylint:disable=invalid-name
    """Delete orphan content units."""
    api.Client(config.get_config()).delete(ORPHANS_PATH)


def _make_user(cfg):
    """A generator to create a user account on the target system.

    Yield a username and private key. The corresponding public key is made the
    one and only key in the user's ``authorized_keys`` file.

    The username and private key are yielded one-by-one rather than as a pair
    because the user creation and key creation steps are executed serially.
    Should the latter fail, the calling function will still be able to delete
    the created user.

    The user is given a home directory. When deleting this user, make sure to
    pass ``--remove`` to ``userdel``. Otherwise, the home directory will be
    left in place.
    """
    client = cli.Client(cfg)
    sudo = '' if utils.is_root(cfg) else 'sudo '

    # According to useradd(8), usernames may be up to 32 characters long. But
    # long names break the rsync publish process: (SNIP == username)
    #
    #     unix_listener:
    #     "/tmp/rsync_distributor-[SNIP]@example.com:22.64tcAiD8em417CiN"
    #     too long for Unix domain socket
    #
    username = utils.uuid4()[:12]
    cmd = 'useradd --create-home {0}'
    client.run((sudo + cmd.format(username)).split())
    yield username

    cmd = 'runuser --shell /bin/sh {} --command'.format(username)
    cmd = (sudo + cmd).split()
    cmd.append('ssh-keygen -N "" -f /home/{}/.ssh/mykey'.format(username))
    client.run(cmd)
    cmd = 'cp /home/{0}/.ssh/mykey.pub /home/{0}/.ssh/authorized_keys'
    client.run((sudo + cmd.format(username)).split())
    cmd = 'cat /home/{0}/.ssh/mykey'
    private_key = client.run((sudo + cmd.format(username)).split()).stdout
    yield private_key


def _get_dists_by_type_id(cfg, repo_href):
    """Return the named repository's distributors, keyed by their type IDs.

    :param pulp_smash.config.ServerConfig cfg: Information about the Pulp
        server being targeted.
    :param repo_href: The path to a repository with a yum distributor.
    :returns: A dict in the form ``{'type_id': {distributor_info}}``.
    """
    dists = api.Client(cfg).get(urljoin(repo_href, 'distributors/')).json()
    return {dist['distributor_type_id']: dist for dist in dists}


class _RsyncDistUtilsMixin(object):  # pylint:disable=too-few-public-methods
    """A mixin providing methods for working with the RPM rsync distributor.

    This mixin requires that the ``unittest.TestCase`` class from the standard
    library is a parent class.
    """

    def make_user(self, cfg):
        """Create a user account with a home directory and an SSH keypair.

        In addition, schedule the user for deletion with ``self.addCleanup``.

        :param pulp_smash.config.ServerConfig cfg: Information about the server
            being targeted.
        :returns: A ``(username, private_key)`` tuple.
        """
        sudo = '' if utils.is_root(cfg) else 'sudo '
        creator = _make_user(cfg)
        username = next(creator)
        self.addCleanup(
            cli.Client(cfg).run,
            (sudo + 'userdel --remove {}').format(username).split()
        )
        private_key = next(creator)
        return (username, private_key)

    def write_private_key(self, cfg, private_key):
        """Write the given private key to a file on disk.

        Ensure that the file is owned by user "apache" and has permissions of
        ``600``. In addition, schedule the key for deletion with
        ``self.addCleanup``.

        :param pulp_smash.config.ServerConfig cfg: Information about the server
            being targeted.
        :returns: The path to the private key on disk, as a string.
        """
        sudo = '' if utils.is_root(cfg) else 'sudo '
        client = cli.Client(cfg)
        ssh_identity_file = client.run(['mktemp']).stdout.strip()
        self.addCleanup(client.run, (sudo + 'rm ' + ssh_identity_file).split())
        client.machine.session().run(
            "echo '{}' > {}".format(private_key, ssh_identity_file)
        )
        client.run(['chmod', '600', ssh_identity_file])
        client.run((sudo + 'chown apache ' + ssh_identity_file).split())
        # Pulp's SELinux policy requires files handled by Pulp to have the
        # httpd_sys_rw_content_t label
        enforcing = client.run(['getenforce']).stdout.strip()
        if enforcing.lower() != 'disabled':
            client.run(
                (sudo + 'chcon -t httpd_sys_rw_content_t ' + ssh_identity_file)
                .split()
            )
        return ssh_identity_file

    def make_repo(self, cfg, dist_cfg_updates):
        """Create a repository with an importer and pair of distributors.

        Create an RPM repository with:

        * A yum importer with a valid feed.
        * A yum distributor.
        * An RPM rsync distributor referencing the yum distributor.

        In addition, schedule the repository for deletion.

        :param pulp_smash.config.ServerConfig cfg: Information about the Pulp
            server being targeted.
        :param dist_cfg_updates: A dict to be merged into the RPM rsync
            distributor's ``distributor_config`` dict. At a minimum, this
            argument should have a value of ``{'remote': {…}}``.
        :returns: The repository's href, as a string.
        """
        api_client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        body['distributors'] = [gen_distributor()]
        body['distributors'].append({
            'distributor_id': utils.uuid4(),
            'distributor_type_id': 'rpm_rsync_distributor',
            'distributor_config': {
                'predistributor_id': body['distributors'][0]['distributor_id'],
            }
        })
        body['distributors'][1]['distributor_config'].update(dist_cfg_updates)
        repo_href = api_client.post(REPOSITORY_PATH, body)['_href']
        self.addCleanup(api_client.delete, repo_href)
        return repo_href

    def verify_publish_is_skip(self, cfg, call_report):
        """Find the 'publish' task and verify it has a result of 'skipped'.

        Recursively search through the tasks named by ``call_report`` for a
        task with a type of ``pulp.server.managers.repo.publish.publish``.
        Assert that only one task has this type, and that this task has a
        result of ``skipped``.

        :param pulp_smash.config.ServerConfig cfg: Information about the Pulp
            server being targeted.
        :param call_report: A call report returned from Pulp after requesting a
            publish; a dict.
        :returns: Nothing.
        """
        tasks = [
            task for task in api.poll_spawned_tasks(cfg, call_report)
            if task['task_type'] == 'pulp.server.managers.repo.publish.publish'
        ]
        self.assertEqual(len(tasks), 1, tasks)
        self.assertEqual(tasks[0]['result']['result'], 'skipped', tasks[0])

    def verify_files_in_dir(self, cfg, distributor_cfg):
        """Verify the RPM rsync distributor has placed RPMs in the given path.

        Verify that path ``{root}/{remote_units_path}/rpm`` exists in the
        target system's filesystem, and that
        :data:`pulp_smash.constants.RPM_FEED_COUNT` RPMs are present in this
        directory.

        :param pulp_smash.config.ServerConfig cfg: Information about the system
            onto which files have been published.
        :param distributor_cfg: A dict of information about an RPM rsync
            distributor.
        :returns: Nothing.
        """
        # This method avoids calling command_string.split() to avoid issues
        # with spaces and other funny character in path names.
        cli_client = cli.Client(cfg)
        sudo = () if utils.is_root(cfg) else ('sudo',)
        path = distributor_cfg['config']['remote']['root']
        remote_units_path = distributor_cfg['config'].get(
            'remote_units_path',
            'content/units',
        )
        for segment in _split_path(remote_units_path):
            cmd = sudo + ('ls', '-1', path)
            files = set(cli_client.run(cmd).stdout.strip().split('\n'))
            self.assertIn(segment, files)
            path = os.path.join(path, segment)
        cmd = sudo + ('find', path, '-name', '*.rpm')
        files = cli_client.run(cmd).stdout.strip().split('\n')
        self.assertEqual(len(files), RPM_FEED_COUNT, files)


class PublishBeforeYumDistTestCase(
        _RsyncDistUtilsMixin,
        unittest.TestCase):
    """Publish a repo with the rsync distributor before the yum distributor.

    Do the following:

    1. Create a repository with a yum distributor and rsync distributor.
    2. Publish with the rpm rsync distributor. Verify that the publish fails.

    This test targets `Pulp #2187 <https://pulp.plan.io/issues/2187>`_.
    """

    def test_all(self):
        """Publish the rpm rsync distributor before the yum distributor."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(2187, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2187')

        # Create a user and a repository.
        ssh_user, priv_key = self.make_user(cfg)
        ssh_identity_file = self.write_private_key(cfg, priv_key)
        repo_href = self.make_repo(cfg, {'remote': {
            'host': urlparse(cfg.base_url).netloc,
            'root': '/home/' + ssh_user,
            'ssh_identity_file': ssh_identity_file,
            'ssh_user': ssh_user,
        }})

        # Publish with the rsync distributor.
        distribs = _get_dists_by_type_id(cfg, repo_href)
        self.verify_publish_is_skip(cfg, api.Client(cfg).post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distribs['rpm_rsync_distributor']['id']}
        ).json())

        # Verify that the rsync distributor hasn't placed files
        sudo = '' if utils.is_root(cfg) else 'sudo '
        cmd = (sudo + 'ls -1 /home/{}'.format(ssh_user)).split()
        dirs = set(cli.Client(cfg).run(cmd).stdout.strip().split('\n'))
        self.assertNotIn('content', dirs)


class ForceFullTestCase(
        _RsyncDistUtilsMixin,
        DisableSELinuxMixin,
        unittest.TestCase):
    """Use the ``force_full`` RPM rsync distributor option.

    Do the following:

    1. Create a repository with a yum distributor and RPM rsync distributor.
       Add content units to the repository.
    2. Publish with the yum distributor.
    3. Publish with the RPM rsync distributor. Verify that the correct files
       are in the target directory.
    4. Remove all files from the target directory. Publish again, and verify
       that:

       * The task for publishing has a result of "skipped."
       * No files are placed in the target directory. (This tests Pulp's
         fast-forward logic.)

    5. Publish with the RPM rsync distributor, with ``force_full`` set to true.
       Verify that files are placed in the target directory. Skip this step if
       `Pulp #2202`_ is not yet fixed.

    Additionally, SELinux is temporarily set to "permissive" mode on the target
    system if `Pulp #2199`_ is not yet fixed.

    .. _Pulp #2199: https://pulp.plan.io/issues/2199
    .. _Pulp #2202: https://pulp.plan.io/issues/2202
    """

    def test_all(self):
        """Use the ``force_full`` RPM rsync distributor option."""
        cfg = config.get_config()
        api_client = api.Client(cfg)
        cli_client = cli.Client(cfg)
        sudo = '' if utils.is_root(cfg) else 'sudo '

        # Create a user and repo with an importer and distribs. Sync the repo.
        ssh_user, priv_key = self.make_user(cfg)
        ssh_identity_file = self.write_private_key(cfg, priv_key)
        repo_href = self.make_repo(cfg, {'remote': {
            'host': urlparse(cfg.base_url).netloc,
            'root': '/home/' + ssh_user,
            'ssh_identity_file': ssh_identity_file,
            'ssh_user': ssh_user,
        }})
        utils.sync_repo(cfg, repo_href)

        # Publish the repo with the yum and rsync distributors, respectively.
        # Verify that the RPM rsync distributor has placed files.
        distribs = _get_dists_by_type_id(cfg, repo_href)
        self.maybe_disable_selinux(cfg, 2199)
        for type_id in ('yum_distributor', 'rpm_rsync_distributor'):
            api_client.post(urljoin(repo_href, 'actions/publish/'), {
                'id': distribs[type_id]['id']
            })
        self.verify_files_in_dir(cfg, distribs['rpm_rsync_distributor'])

        # Remove all files from the target directory, and publish again. Verify
        # that the RPM rsync distributor didn't place any files.
        cmd = sudo + 'rm -rf /home/{}/content'.format(ssh_user)
        cli_client.run(cmd.split())
        self.verify_publish_is_skip(cfg, api_client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distribs['rpm_rsync_distributor']['id']}
        ).json())
        cmd = sudo + 'ls -1 /home/{}'.format(ssh_user)
        dirs = set(cli_client.run(cmd.split()).stdout.strip().split('\n'))
        self.assertNotIn('content', dirs)

        # Publish the repo with ``force_full`` set to true. Verify that the RPM
        # rsync distributor placed files.
        if selectors.bug_is_untestable(2202, cfg.version):
            return
        api_client.post(urljoin(repo_href, 'actions/publish/'), {
            'id': distribs['rpm_rsync_distributor']['id'],
            'override_config': {'force_full': True},
        })
        self.verify_files_in_dir(cfg, distribs['rpm_rsync_distributor'])


class VerifyOptionsTestCase(_RsyncDistUtilsMixin, unittest.TestCase):
    """Test Pulp's verification of RPM rsync distributor configuration options.

    Do the following:

    * Repeatedly attempt to create an RPM repository with an importer and pair
      of distributors. Each time, pass an invalid option, or omit a required
      option.
    * Create an RPM repository with an importer and pair of distributors. Pass
      valid configuration options. This demonstrates that creation failures are
      due to Pulp's validation logic, not some other factor.
    """

    @classmethod
    def setUpClass(cls):
        """Create a value for the rsync distrib's ``remote`` config section.

        Using the same config for each of the test methods allows the test
        methods to behave more similarly.
        """
        cls.cfg = config.get_config()
        ssh_user = utils.uuid4()[:12]
        cls.remote = {
            'host': 'example.com',
            'root': '/home/' + ssh_user,
            'ssh_identity_file': '/' + utils.uuid4(),
            'ssh_user': ssh_user,
        }
        cls._remote = cls.remote.copy()

    def tearDown(self):
        """Verify that the ``remote`` config section hasn't changed."""
        # We could also create a setUp() that executes `self.remote =
        # self.remote.copy()`, thus shadowing the class var. However, that
        # would merely mask a mis-behaving test method. This assertion lets us
        # discover it instead.
        self.assertEqual(self.remote, self._remote)

    def test_success(self):
        """Successfully create an RPM repo with importers and distributors."""
        self.make_repo(self.cfg, {'remote': self.remote})

    def test_required_options(self):
        """Omit each of the required RPM rsync distributor config options."""
        for key in self.remote:
            remote = self.remote.copy()
            remote.pop(key)
            with self.subTest(remote=remote):
                with self.assertRaises(HTTPError):
                    self.make_repo(self.cfg, {'remote': remote})

    def test_predistributor_id(self):
        """Pass a bogus ID as the ``predistributor_id`` config option."""
        if selectors.bug_is_untestable(2191, self.cfg.version):
            raise self.skipTest('https://pulp.plan.io/issues/2191')
        api_client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        body['distributors'] = [gen_distributor()]
        body['distributors'].append({
            'distributor_id': utils.uuid4(),
            'distributor_type_id': 'rpm_rsync_distributor',
            'distributor_config': {
                'predistributor_id': utils.uuid4(),
                'remote': self.remote,
            }
        })
        try:
            with self.assertRaises(HTTPError, msg=body):
                repo_href = api_client.post(REPOSITORY_PATH, body)['_href']
        except AssertionError as err:
            self.addCleanup(api_client.delete, repo_href)
            raise err

    def test_root(self):
        """Pass a relative path to the ``root`` configuration option."""
        if selectors.bug_is_untestable(2192, self.cfg.version):
            raise self.skipTest('https://pulp.plan.io/issues/2192')
        remote = self.remote.copy()
        remote['root'] = remote['root'][1:]
        with self.assertRaises(HTTPError, msg=remote):
            self.make_repo(self.cfg, {'remote': remote})

    def test_remote_units_path(self):
        """Pass an absolute path to the ``remote_units_path`` config option."""
        remote = self.remote.copy()
        remote['remote_units_path'] = '/foo'
        with self.assertRaises(HTTPError, msg=remote):
            self.make_repo(self.cfg, {'remote': remote})


class RemoteUnitsPathTestCase(
        _RsyncDistUtilsMixin,
        DisableSELinuxMixin,
        unittest.TestCase):
    """Exercise the ``remote_units_path`` option.

    Do the following:

    1. Create a repository with a yum distributor and RPM rsync distributor,
       and ensure that the latter distributor's ``remote_units_path`` option is
       set to a non-default value (not ``content/units``). Add content units to
       the repository.
    2. Publish with the yum distributor.
    3. Publish with the RPM rsync distributor. Verify that files are placed in
       the correct directory.
    4. Publish with the RPM rsync distributor, with ``remote_units_path``
       passed as publish option. Verify that files are placed in this
       directory.
    """

    def test_all(self):
        """Exercise the ``remote_units_path`` option."""
        cfg = config.get_config()
        api_client = api.Client(cfg)
        # We already know Pulp can deal with 2-segment paths, due to the
        # default remote_units_path of 'content/units'.
        paths = (
            os.path.join(*[utils.uuid4() for _ in range(3)]),
            os.path.join(*[utils.uuid4() for _ in range(1)]),
        )

        # Create a user and repo with an importer and distribs. Sync the repo.
        ssh_user, priv_key = self.make_user(cfg)
        ssh_identity_file = self.write_private_key(cfg, priv_key)
        repo_href = self.make_repo(cfg, {
            'remote': {
                'host': urlparse(cfg.base_url).netloc,
                'root': '/home/' + ssh_user,
                'ssh_identity_file': ssh_identity_file,
                'ssh_user': ssh_user,
            },
            'remote_units_path': paths[0],
        })
        distribs = _get_dists_by_type_id(cfg, repo_href)
        utils.sync_repo(cfg, repo_href)

        # Publish the repo with the yum and rpm rsync distributors,
        # respectively. Verify that files have been correctly placed.
        distribs = _get_dists_by_type_id(cfg, repo_href)
        self.maybe_disable_selinux(cfg, 2199)
        for type_id in ('yum_distributor', 'rpm_rsync_distributor'):
            api_client.post(urljoin(repo_href, 'actions/publish/'), {
                'id': distribs[type_id]['id'],
                'config': {'remote_units_path': paths[1]},
            })
        distribs['rpm_rsync_distributor']['remote_units_path'] = paths[1]
        self.verify_files_in_dir(cfg, distribs['rpm_rsync_distributor'])


class DeleteTestCase(
        _RsyncDistUtilsMixin,
        DisableSELinuxMixin,
        unittest.TestCase):
    """Use the ``delete`` RPM rsync distributor option.

    Do the following:

    1. Create a repository with a yum distributor and RPM rsync distributor.
       Add content units to the repository.
    2. Publish with the yum distributor.
    3. Publish with the RPM rsync distributor. Verify that the correct files
       are in the target directory.
    4. Remove all files from the repository, and publish with the yum
       distributor.
    5. Publish with the RPM rsync distributor, with ``delete`` set to true.
       Verify that all files are removed from the target directory.

    This test targets `Pulp #2221 <https://pulp.plan.io/issues/2221>`_.
    """

    def test_all(self):
        """Use the ``delete`` RPM rsync distributor option."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(2221, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2221')
        api_client = api.Client(cfg)

        # Create a user and repo with an importer and distribs. Sync the repo.
        ssh_user, priv_key = self.make_user(cfg)
        ssh_identity_file = self.write_private_key(cfg, priv_key)
        repo_href = self.make_repo(cfg, {'remote': {
            'host': urlparse(cfg.base_url).netloc,
            'root': '/home/' + ssh_user,
            'ssh_identity_file': ssh_identity_file,
            'ssh_user': ssh_user,
        }})
        utils.sync_repo(cfg, repo_href)

        # Publish the repo with the yum and rsync distributors, respectively.
        # Verify that the RPM rsync distributor has placed files.
        distribs = _get_dists_by_type_id(cfg, repo_href)
        self.maybe_disable_selinux(cfg, 2199)
        for type_id in ('yum_distributor', 'rpm_rsync_distributor'):
            api_client.post(urljoin(repo_href, 'actions/publish/'), {
                'id': distribs[type_id]['id']
            })
        self.verify_files_in_dir(cfg, distribs['rpm_rsync_distributor'])

        # Disassociate all units from the repo, publish the repo, and verify.
        api_client.post(urljoin(repo_href, 'actions/unassociate/'), {
            'criteria': {}
        })
        api_client.post(urljoin(repo_href, 'actions/publish/'), {
            'id': distribs['yum_distributor']['id']
        })
        self._verify_units_not_in_repo(cfg, repo_href)

        # Publish with the RPM rsync distributor, and verify that no RPMs are
        # in the target directory.
        api_client.post(urljoin(repo_href, 'actions/publish/'), {
            'id': distribs['rpm_rsync_distributor']['id'],
            'override_config': {'delete': True},
        })
        self._verify_files_not_in_dir(cfg, distribs['rpm_rsync_distributor'])

    def _verify_units_not_in_repo(self, cfg, repo_href):
        """Verify no content units are in the specified repository."""
        repo = api.Client(cfg).get(repo_href).json()
        for key, val in repo['content_unit_counts'].items():
            with self.subTest(key=key):
                self.assertEqual(val, 0)

    def _verify_files_not_in_dir(self, cfg, distributor_cfg):
        """Verify no RPMs are in the distributor's ``remote_units_path``."""
        path = os.path.join(
            distributor_cfg['config']['remote']['root'],
            distributor_cfg['config'].get('remote_units_path', 'content/units')
        )
        cmd = ['find', path, '-name', '*.rpm']
        if not utils.is_root(cfg):
            cmd.insert(0, 'sudo')
        files = cli.Client(cfg).run(cmd).stdout.strip().split('\n')
        self.assertEqual(len(files), 0, files)
