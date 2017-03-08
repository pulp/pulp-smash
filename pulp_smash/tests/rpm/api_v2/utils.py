# coding=utf-8
"""Utility functions for RPM API tests."""
import gzip
import io
import time
import unittest
from os.path import basename
from urllib.parse import urljoin
from xml.etree import ElementTree

from pulp_smash import api, cli, exceptions, selectors, utils
from pulp_smash.constants import RPM_NAMESPACES


def gen_repo():
    """Return a semi-random dict for use in creating an RPM repository."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'yum_importer',
        'notes': {'_repo-type': 'rpm-repo'},
    }


def gen_repo_group():
    """Return a semi-random dict for use in creating a RPM repository group."""
    return {
        'id': utils.uuid4(),
    }


def gen_distributor():
    """Return a semi-random dict for use in creating a YUM distributor."""
    return {
        'auto_publish': False,
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'yum_distributor',
        'distributor_config': {
            'http': True,
            'https': True,
            'relative_url': utils.uuid4() + '/',
        },
    }


def get_repodata_repomd_xml(cfg, distributor, response_handler=None):
    """Download the given repository's ``repodata/repomd.xml`` file.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param distributor: A dict of information about a repository distributor.
    :param response_handler: The callback function used by
        :class:`pulp_smash.api.Client` after downloading the ``repomd.xml``
        file. Defaults to :func:`xml_handler`. Use
        :func:`pulp_smash.api.safe_handler` if you want the raw response.
    :returns: Whatever is dictated by ``response_handler``.
    """
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    if not path.endswith('/'):
        path += '/'
    path = urljoin(path, 'repodata/repomd.xml')
    if response_handler is None:
        response_handler = xml_handler
    return api.Client(cfg, response_handler).get(path)


def get_repodata(
        cfg,
        distributor,
        type_,
        response_handler=None,
        repomd_xml=None):
    """Download a file of the given ``type_`` from a ``repodata/`` directory.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param distributor: A dict of information about a repository distributor.
    :param type_: The type of file to fetch from a repository's ``repodata/``
        directory. Valid values might be "updateinfo" or "group".
    :param response_handler: The callback function used by
        :class:`pulp_smash.api.Client` after downloading the ``repomd.xml``
        file. Defaults to :func:`xml_handler`. Use
        :func:`pulp_smash.api.safe_handler` if you want the raw response.
    :param repomd_xml: A ``repomd.xml`` file as an ``ElementTree``. If not
        given, :func:`get_repodata_repomd_xml` is consulted.
    :returns: Whatever is dictated by ``response_handler``.
    """
    # Download and search through ``.../repodata/repomd.xml``.
    if repomd_xml is None:
        repomd_xml = get_repodata_repomd_xml(cfg, distributor)
    xpath = (
        "{{{namespace}}}data[@type='{type_}']/{{{namespace}}}location"
        .format(namespace=RPM_NAMESPACES['metadata/repo'], type_=type_)
    )
    location_elements = repomd_xml.findall(xpath)
    if len(location_elements) != 1:
        raise ValueError(
            'The given "repomd.xml" file should contain one matching '
            '"location" element, but {} were found with the XPath selector {}'
            .format(len(location_elements), xpath)
        )

    # Build the URL to the file of the requested `type_`.
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    if not path.endswith('/'):
        path += '/'
    path = urljoin(path, location_elements[0].get('href'))
    if response_handler is None:
        response_handler = xml_handler
    return api.Client(cfg, response_handler).get(path)


def xml_handler(_, response):
    """Decode a response as if it is XML.

    This API response handler is useful for fetching XML files made available
    by an RPM repository. When it handles a response, it will check the status
    code of ``response``, decompress the response if the request URL ended in
    ``.gz``, and return an ``xml.etree.Element`` instance built from the
    response body.

    Note:

    * The entire response XML is loaded and parsed before returning, so this
      may be unsafe for use with large XML files.
    * The ``Content-Type`` and ``Content-Encoding`` response headers are
      ignored due to https://pulp.plan.io/issues/1781.
    """
    response.raise_for_status()
    if response.request.url.endswith('.gz'):  # See bug referenced in docstring
        with io.BytesIO(response.content) as compressed:
            with gzip.GzipFile(fileobj=compressed) as decompressed:
                xml_bytes = decompressed.read()
    else:
        xml_bytes = response.content
    # A well-formed XML document begins with a declaration like this:
    #
    #     <?xml version="1.0" encoding="UTF-8"?>
    #
    # We are trusting the parser to handle this correctly.
    return ElementTree.fromstring(xml_bytes)


class DisableSELinuxMixin(object):  # pylint:disable=too-few-public-methods
    """A mixin providing the ability to temporarily disable SELinux."""

    def maybe_disable_selinux(self, cfg, pulp_issue_id):
        """Disable SELinux if appropriate.

        If the given Pulp issue is unresolved, and if SELinux is installed and
        enforcing on the target Pulp system, then disable SELinux and schedule
        it to be re-enabled. (Method ``addCleanup`` is used for the schedule.)

        :param pulp_smash.config.PulpSmashConfig cfg: Information about the
            Pulp deployment being targeted.
        :param pulp_issue_id: The (integer) ID of a `Pulp issue`_. If the
            referenced issue is fixed in the Pulp system under test, this
            method immediately returns.
        :returns: Nothing.

        .. _Pulp issue: https://pulp.plan.io/issues/
        """
        # Abort if the Pulp issue is resolved, if SELinux is not installed or
        # if SELinux is not enforcing.
        #
        # NOTE: Hard-coding the absolute path to a command is a Bad Idea™.
        # However, non-login non-root shells may have short PATH environment
        # variables. For example:
        #
        #     /usr/lib64/qt-3.3/bin:/usr/local/bin:/usr/bin
        #
        # We cannot execute `PATH=${PATH}:/usr/sbin which getenforce` because
        # Plumbum does a good job of preventing shell expansions. See:
        # https://github.com/PulpQE/pulp-smash/issues/89
        if selectors.bug_is_testable(pulp_issue_id, cfg.version):
            return
        client = cli.Client(cfg, cli.echo_handler)
        cmd = 'test -e /usr/sbin/getenforce'.split()
        if client.run(cmd).returncode != 0:
            return
        client.response_handler = cli.code_handler
        cmd = ['/usr/sbin/getenforce']
        if client.run(cmd).stdout.strip().lower() != 'enforcing':
            return

        # Temporarily disable SELinux.
        sudo = '' if utils.is_root(cfg) else 'sudo '
        cmd = (sudo + 'setenforce 0').split()
        client.run(cmd)
        cmd = (sudo + 'setenforce 1').split()
        self.addCleanup(client.run, cmd)


class TemporaryUserMixin(object):
    """A mixin providing the ability to create a temporary user.

    A typical usage of this mixin is as follows:

    .. code-block:: python

        ssh_user, priv_key = self.make_user(cfg)
        ssh_identity_file = self.write_private_key(cfg, priv_key)

    This mixin requires that the ``unittest.TestCase`` class from the standard
    library be a parent class.
    """

    def make_user(self, cfg):
        """Create a user account with a home directory and an SSH keypair.

        In addition, schedule the user for deletion with ``self.addCleanup``.

        :param pulp_smash.config.PulpSmashConfig cfg: Information about the
            host being targeted.
        :returns: A ``(username, private_key)`` tuple.
        """
        creator = self._make_user(cfg)
        username = next(creator)
        self.addCleanup(self.delete_user, cfg, username)
        private_key = next(creator)
        return (username, private_key)

    @staticmethod
    def _make_user(cfg):
        """Create a user account on a target system.

        This method is implemented as a generator. When executed, it will yield
        a username and private key. The corresponding public key is made the
        one and only key in the user's ``authorized_keys`` file.

        The username and private key are yielded one-by-one rather than as a
        pair because the user creation and key creation steps are executed
        serially.  Should the latter fail, the calling function will still be
        able to delete the created user.

        The user is given a home directory. When deleting this user, make sure
        to pass ``--remove`` to ``userdel``. Otherwise, the home directory will
        be left in place.
        """
        client = cli.Client(cfg)
        sudo = '' if utils.is_root(cfg) else 'sudo '

        # According to useradd(8), usernames may be up to 32 characters long.
        # But long names break the rsync publish process: (SNIP == username)
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

    @staticmethod
    def delete_user(cfg, username):
        """Delete a user.

        The Pulp rsync distributor has a habit of leaving (idle?) SSH sessions
        open even after publishing a repository. When executed, this function
        will:

        1. Poll the process list until all processes belonging to ``username``
           have died, or raise a ``unittest.SkipTest`` exception if the time
           limit is exceeded.
        2. Delete ``username``.
        """
        sudo = () if utils.is_root(cfg) else ('sudo',)
        client = cli.Client(cfg)

        # values are arbitrary
        iter_time = 2  # seconds
        iter_limit = 15  # unitless

        # Wait for user's processes to die.
        cmd = sudo + ('ps', '-wwo', 'args', '--user', username, '--no-headers')
        i = 0
        while i <= iter_limit:
            try:
                user_processes = client.run(cmd).stdout.splitlines()
            except exceptions.CalledProcessError:
                break
            i += 1
            time.sleep(iter_time)
        else:
            raise unittest.SkipTest(
                'User still has processes running after {}+ seconds. Aborting '
                'test. User processes: {}'
                .format(iter_time * iter_limit, user_processes)
            )

        # Delete user.
        cmd = sudo + ('userdel', '--remove', username)
        client.run(cmd)

    def write_private_key(self, cfg, private_key):
        """Write the given private key to a file on disk.

        Ensure that the file is owned by user "apache" and has permissions of
        ``600``. In addition, schedule the key for deletion with
        ``self.addCleanup``.

        :param pulp_smash.config.PulpSmashConfig cfg: Information about the
            host being targeted.
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


def get_unit(cfg, distributor, unit_name, primary_xml=None):
    """Download a file from a published repository.

    A typical invocation is as follows:

        >>> foo_rpm = get_unit(cfg, repo['distributors'][0], 'foo.rpm')

    If multiple units are being fetched, efficiency can be improved by passing
    in a parsed ``primary.xml`` file:

        >>> distributor = repo['distributors'][0]
        >>> primary_xml = get_repodata(cfg, distributor, 'primary')
        >>> foo_rpm = get_unit(cfg, distributor, 'foo.rpm', primary_xml)
        >>> bar_rpm = get_unit(cfg, distributor, 'bar.rpm', primary_xml)

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param distributor: A dict of information about a repository distributor.
    :param unit_name: The name of a content unit to be fetched. For example:
        "bear-4.1-1.noarch.rpm".
    :param primary_xml: A ``primary.xml`` file as an ``ElementTree``. If not
        given, :func:`get_repodata` is consulted.
    :returns: A raw response. The unit is available as ``response.content``.
    """
    if primary_xml is None:
        primary_xml = get_repodata(cfg, distributor, 'primary')

    # Create a dict in the form {foo.rpm: Packages/f/foo.rpm}
    xpath = '{{{}}}package'.format(RPM_NAMESPACES['metadata/common'])
    packages = primary_xml.findall(xpath)
    xpath = '{{{}}}location'.format(RPM_NAMESPACES['metadata/common'])
    hrefs = [package.find(xpath).get('href') for package in packages]
    href_map = {basename(href): href for href in hrefs}
    href = href_map[unit_name]

    # Fetch the unit.
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    if not path.endswith('/'):
        path += '/'
    path = urljoin(path, href)
    return api.Client(cfg).get(path)


def get_dists_by_type_id(cfg, repo):
    """Return the named repository's distributors, keyed by their type IDs.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param repo_href: A dict of information about a repository.
    :returns: A dict in the form ``{'type_id': {distributor_info}}``.
    """
    dists = api.Client(cfg).get(urljoin(repo['_href'], 'distributors/')).json()
    return {dist['distributor_type_id']: dist for dist in dists}


def set_pulp_manage_rsync(cfg, boolean):
    """Set the ``pulp_manage_rsync`` SELinux policy.

    If the ``semanage`` executable is not available, return. (This is the case
    if SELinux isn't installed on the system under test.) Otherwise, set the
    ``pulp_manage_rsync SELinux policy on or off, depending on the truthiness
    of ``boolean``.

    For more information on the ``pulp_manage_rsync`` SELinux policy, see `ISO
    rsync Distributor → Configuration
    <http://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/iso-rsync-distributor.html#configuration>`_.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param boolean: Either ``True`` or ``False``.
    :returns: Information about the executed command, or ``None`` if no command
        was executed.
    :rtype: pulp_smash.cli.CompletedProcess
    """
    sudo = () if utils.is_root(cfg) else ('sudo',)
    client = cli.Client(cfg)
    try:
        # semanage is installed at /sbin/semanage on some distros, and requires
        # root privileges to discover.
        client.run(sudo + ('which', 'semanage'))
    except exceptions.CalledProcessError:
        return
    cmd = sudo
    cmd += ('semanage', 'boolean', '--modify')
    cmd += ('--on',) if boolean else ('--off',)
    cmd += ('pulp_manage_rsync',)
    return client.run(cmd)
