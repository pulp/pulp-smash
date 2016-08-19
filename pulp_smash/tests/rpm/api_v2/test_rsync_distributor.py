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
from __future__ import unicode_literals

import unittest2

from pulp_smash import api, cli, config, exceptions, selectors, utils
from pulp_smash.compat import urljoin, urlparse
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip the tests in this module.

    Skip the tests in this module if:

    * The RPM plugin is not installed on the target Pulp server.
    * `Pulp #1759`_ is not implemented on the target Pulp server.

    .. _Pulp #1759: https://pulp.plan.io/issues/1759
    """
    set_up_module()
    if selectors.bug_is_untestable(1759, config.get_config().version):
        raise unittest2.SkipTest('https://pulp.plan.io/issues/1759')


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

    cmd = 'runuser -u {0} -- ssh-keygen -N . -f /home/{0}/.ssh/mykey'
    cmd = (sudo + cmd.format(username)).split()
    cmd[cmd.index('-N') + 1] = ''
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
        return ssh_identity_file

    def make_repo(self, cfg, remote):
        """Create a repository with an importer and pair of distributors.

        Create an RPM repository with:

        * A yum importer with a valid feed.
        * A yum distributor.
        * An RPM rsync distributor referencing the yum distributor.

        In addition, schedule the repository for deletion.

        :param pulp_smash.config.ServerConfig cfg: Information about the Pulp
            server being targeted.
        :param remote: A dict for the RPM rsync distributor's ``remote``
            section.
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
                'remote': remote,
            }
        })
        repo_href = api_client.post(REPOSITORY_PATH, body)['_href']
        self.addCleanup(api_client.delete, repo_href)
        return repo_href


class PublishBeforeYumDistTestCase(
        _RsyncDistUtilsMixin,
        utils.BaseAPITestCase):
    """Publish a repo with the rsync distributor before the yum distributor.

    Do the following:

    1. Create a repository with a yum distributor and rsync distributor.
    2. Publish with the rpm rsync distributor. Verify that the publish fails.
    """

    def test_all(self):
        """Publish the rpm rsync distributor before the yum distributor."""
        # Create a user and a repository.
        ssh_user, priv_key = self.make_user(self.cfg)
        ssh_identity_file = self.write_private_key(self.cfg, priv_key)
        repo_href = self.make_repo(self.cfg, {
            'host': urlparse(self.cfg.base_url).netloc,
            'root': '/home/' + ssh_user,
            'ssh_identity_file': ssh_identity_file,
            'ssh_user': ssh_user,
        })

        # Publish with the rsync distributor.
        dists_by_type_id = _get_dists_by_type_id(self.cfg, repo_href)
        with self.assertRaises(exceptions.TaskReportError):
            api.Client(self.cfg).post(urljoin(repo_href, 'actions/publish/'), {
                'id': dists_by_type_id['rpm_rsync_distributor']['id'],
            })

        # Verify that the rsync distributor hasn't placed files
        sudo = '' if utils.is_root(self.cfg) else 'sudo '
        cmd = (sudo + 'ls -1 /home/{}'.format(ssh_user)).split()
        dirs = set(cli.Client(self.cfg).run(cmd).stdout.strip().split('\n'))
        self.assertNotIn('content', dirs)


class PublishTestCase(_RsyncDistUtilsMixin, utils.BaseAPITestCase):
    """Publish a repository with the rsync distributor.

    Do the following:

    1. Create a repository with a yum distributor and rsync distributor. Add
       content units to the repository.
    2. Publish with the yum distributor.
    3. Publish with the rpm rsync distributor. Verify that the correct files
       are in the target directory.
    """

    def test_all(self):
        """Publish a repository several times with the rsync distributor."""
        # Create a user and a repository. Sync the repo.
        ssh_user, priv_key = self.make_user(self.cfg)
        ssh_identity_file = self.write_private_key(self.cfg, priv_key)
        repo_href = self.make_repo(self.cfg, {
            'host': urlparse(self.cfg.base_url).netloc,
            'root': '/home/' + ssh_user,
            'ssh_identity_file': ssh_identity_file,
            'ssh_user': ssh_user,
        })
        utils.sync_repo(self.cfg, repo_href)

        # Publish with the yum and rsync distributors.
        api_client = api.Client(self.cfg)
        dists_by_type_id = _get_dists_by_type_id(self.cfg, repo_href)
        for type_id in ('yum_distributor', 'rpm_rsync_distributor'):
            body = {'id': dists_by_type_id[type_id]['id']}
            api_client.post(urljoin(repo_href, 'actions/publish/'), body)

        # Verify what the rsync distributor has done
        cli_client = cli.Client(self.cfg)
        sudo = '' if utils.is_root(self.cfg) else 'sudo '

        cmd = sudo + 'ls -1 /home/{}'.format(ssh_user)
        dirs = set(cli_client.run(cmd.split()).stdout.strip().split('\n'))
        self.assertGreaterEqual(dirs, {'content'})

        cmd = sudo + 'ls -1 /home/{}/content'.format(ssh_user)
        dirs = set(cli_client.run(cmd.split()).stdout.strip().split('\n'))
        self.assertGreaterEqual(dirs, {'units'})

        cmd = sudo + 'ls -1 /home/{}/content/units'.format(ssh_user)
        dirs = set(cli_client.run(cmd.split()).stdout.strip().split('\n'))
        self.assertGreaterEqual(dirs, {'rpm'})

        cmd = (sudo + (
            'find /home/{}/content/units/rpm/ -name *.rpm'.format(ssh_user)
        ))
        files = cli_client.run(cmd.split()).stdout.strip().split('\n')
        self.assertEqual(len(files), 32, files)
