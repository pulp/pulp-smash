# coding=utf-8
"""A client for working with Pulp systems via their CLI."""
import contextlib
import os
import socket
from urllib.parse import urlparse

import plumbum

from pulp_smash import exceptions


# A dict mapping hostnames to *nix service managers.
#
# For example: {'old.example.com': 'sysv', 'new.example.com', 'systemd'}
_SERVICE_MANAGERS = {}

# A dict mapping hostnames to *nix package managers.
#
# For example: {'old.example.com': 'yum', 'new.example.com', 'yum'}
_PACKAGE_MANAGERS = {}


def _get_hostname(urlstring):
    """Get the hostname from a URL string.

    ``urlparse`` follows RFC 1808 and requires that network locations be
    prefixed with "//". This function is a thin wrapper. It treats the leading
    "//" as optional::

    >>> urls = ('ftp://localhost', '//localhost', 'localhost', 'localhost:123')
    >>> for url in urls:
    ...     print((_get_hostname(url), urlparse(url).hostname))
    ('localhost', 'localhost')
    ('localhost', 'localhost')
    ('localhost', None)
    ('localhost', None)

    Usage::

        if server_config is None:
            server_config = get_config()
        hostname = _get_hostname(server_config.base_url)

    :param urlstring: A string such as "localhost:3000", "pulp.example.com" or
        "https://pulp.example.com".
    :returns: A hostname, such as "localhost" or "pulp.example.com".

    """
    parts = urlparse(urlstring)
    if parts.hostname is None:
        return _get_hostname('//' + parts.path)
    else:
        return parts.hostname


def _is_root(cfg):
    """Tell if we are root on the target system.

    :param pulp_smash.config.ServerConfig cfg: Information about the target
        system.
    :returns: Either ``True`` or ``False``.
    """
    if Client(cfg).run(('id', '-u')).stdout.strip() == '0':
        return True
    return False


def echo_handler(completed_proc):
    """Immediately return ``completed_proc``."""
    return completed_proc


def code_handler(completed_proc):
    """Check the process for a non-zero return code. Return the process.

    Check the return code by calling ``completed_proc.check_returncode()``.
    See: :meth:`pulp_smash.cli.CompletedProcess.check_returncode`.
    """
    completed_proc.check_returncode()
    return completed_proc


class CompletedProcess(object):
    # pylint:disable=too-few-public-methods
    """A process that has finished running.

    This class is similar to the ``subprocess.CompletedProcess`` class
    available in Python 3.5 and above. Significant differences include the
    following:

    * All constructor arguments are required.
    * :meth:`check_returncode` returns a custom exception, not
      ``subprocess.CalledProcessError``.

    All constructor arguments are stored as instance attributes.

    :param args: A string or a sequence. The arguments passed to
        :meth:`pulp_smash.cli.Client.run`.
    :param returncode: The integer exit code of the executed process. Negative
        for signals.
    :param stdout: The standard output of the executed process.
    :param stderr: The standard error of the executed process.
    """

    def __init__(self, args, returncode, stdout, stderr):
        """Initialize a new object."""
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        """Provide an ``eval``-compatible string representation."""
        str_kwargs = ', '.join([
            'args={!r}'.format(self.args),
            'returncode={!r}'.format(self.returncode),
            'stdout={!r}'.format(self.stdout),
            'stderr={!r}'.format(self.stderr),
        ])
        return '{}({})'.format(type(self).__name__, str_kwargs)

    def check_returncode(self):
        """Raise an exception if ``returncode`` is non-zero.

        Raise :class:`pulp_smash.exceptions.CalledProcessError` if
        ``returncode`` is non-zero.

        Why not raise ``subprocess.CalledProcessError``? Because stdout and
        stderr are not included when str() is called on a CalledProcessError
        object. A typical message is::

            "Command '('ls', 'foo')' returned non-zero exit status 2"

        This information is valuable. One could still make
        ``subprocess.CalledProcessError`` work by overloading ``args``:

        >>> if isinstance(args, (str, bytes)):
        ...     custom_args = (args, stdout, stderr)
        ... else:
        ...     custom_args = tuple(args) + (stdout, stderr)
        >>> subprocess.CalledProcessError(args, returncode)

        But this seems like a hack.

        In addition, it's generally good for an application to raise expected
        exceptions from its own namespace, so as to better abstract away
        dependencies.
        """
        if self.returncode != 0:
            raise exceptions.CalledProcessError(
                self.args,
                self.returncode,
                self.stdout,
                self.stderr,
            )


class Client(object):  # pylint:disable=too-few-public-methods
    """A convenience object for working with a CLI.

    This class provides the ability to execute shell commands on either the
    local system or a remote system. Here is a simple usage example:

    >>> from pulp_smash import cli, config
    >>> server_config = config.ServerConfig('localhost')
    >>> client = cli.Client(server_config)
    >>> response = client.run(('echo', '-n', 'foo'))
    >>> response.returncode == 0
    True
    >>> response.stdout == 'foo'
    True
    >>> response.stderr == ''
    True

    You can customize how commands are executed and how responses are handled
    by fiddling with the two public instance attributes:

    ``machine``
        A `Plumbum`_ machine. :meth:`run` delegates all command execution
        responsibilities to this object.
    ``response_handler``
        A callback function. Each time ``machine`` executes a command, the
        result is handed to this callback, and the callback's return value is
        handed to the user.

    If ``server_config.cli_transport`` is ``'local'`` or ``'ssh``, set
    ``machine`` so that commands run locally or over SSH, respectively. If
    ``server_config.cli_transport`` is ``None``, guess how to set ``machine``
    by comparing the hostname embedded in ``server_config.base_url`` against
    the current system's hostname. If they match, set ``machine`` to execute
    commands locally; and vice versa.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        system on which commands will be executed.
    :param response_handler: A callback function. Defaults to
        :func:`pulp_smash.cli.code_handler`.

    .. _Plumbum: http://plumbum.readthedocs.io/en/latest/index.html
    """

    def __init__(self, server_config, response_handler=None):
        """Initialize this object with needed instance attributes."""
        # How do we make requests?
        hostname = _get_hostname(server_config.base_url)
        if server_config.cli_transport is None:
            transport = 'local' if hostname == socket.getfqdn() else 'ssh'
        else:
            transport = server_config.cli_transport
        if transport == 'local':
            self.machine = plumbum.machines.local
        else:  # transport == 'ssh'
            # The SshMachine is a wrapper around the system's "ssh" binary.
            # Thus, it uses ~/.ssh/config, ~/.ssh/known_hosts, etc.
            self.machine = (  # pylint:disable=redefined-variable-type
                plumbum.machines.SshMachine(hostname)
            )

        # How do we handle responses?
        if response_handler is None:
            self.response_handler = code_handler
        else:
            self.response_handler = response_handler

    def run(self, args, **kwargs):
        """Run a command and ``return self.response_handler(result)``.

        This method is a thin wrapper around Plumbum's `BaseCommand.run`_
        method, which is itself a thin wrapper around the standard library's
        `subprocess.Popen`_ class. See their documentation for detailed usage
        instructions. See :class:`pulp_smash.cli.Client` for a usage example.

        .. _BaseCommand.run:
           http://plumbum.readthedocs.io/en/latest/api/commands.html#plumbum.commands.base.BaseCommand.run
        .. _subprocess.Popen:
           https://docs.python.org/3/library/subprocess.html#subprocess.Popen
        """
        # Let self.response_handler check return codes. See:
        # https://plumbum.readthedocs.io/en/latest/api/commands.html#plumbum.commands.base.BaseCommand.run
        kwargs.setdefault('retcode')

        code, stdout, stderr = self.machine[args[0]].run(args[1:], **kwargs)
        completed_process = CompletedProcess(args, code, stdout, stderr)
        return self.response_handler(completed_process)


class ServiceManager(object):
    """A service manager on a system.

    Each instance of this class represents the service manager on a system. An
    example may help to clarify this idea:

    from pulp_smash import cli, config
    >>> svc_mgr = cli.ServiceManager(config.get_config())
    >>> completed_process = svc_manager.stop(['httpd'])
    >>> completed_process = svc_manager.start(['httpd'])

    In the example above, the ``svc_mgr`` object represents the service manager
    on the host referenced by :func:`pulp_smash.config.get_config`.

    Upon instantiation, a :class:`ServiceManager` object talks to its target
    system and uses simple heuristics to determine which service manager is
    available. As a result, it's possible to manage services on heterogeneous
    systems with homogeneous commands.

    Upon instantiation, a :class:`ServiceManager` object also talks to its
    target system and determines whether it is running as root. If not root,
    all commands are prefixed with "sudo". Please ensure that Pulp Smash can
    either execute commands as root or can successfully execute ``sudo``. You
    may need to edit your ``~/.ssh/config`` file.

    :param pulp_smash.config.ServerConfig cfg: Information about the target
        system.
    :raises pulp_smash.exceptions.NoKnownServiceManagerError: If unable to find
        any service manager on the target system.
    """

    def __init__(self, cfg):
        """Initialize a new object."""
        self._client = Client(cfg)
        self._sudo = () if _is_root(cfg) else ('sudo',)
        self._svc_mgr = self._get_service_manager(cfg)
        self._on_jenkins = 'JENKINS_HOME' in os.environ

    @staticmethod
    def _get_service_manager(server_config):
        """Talk to the target system and determine the type of service manager.

        Return "systemd" or "sysv" if the service manager appears to be one of
        those. Raise an exception otherwise.
        """
        hostname = _get_hostname(server_config.base_url)
        try:
            return _SERVICE_MANAGERS[hostname]
        except KeyError:
            pass

        client = Client(server_config, echo_handler)
        commands_managers = (
            ('which systemctl', 'systemd'),
            ('which service', 'sysv'),
            ('test -x /sbin/service', 'sysv'),
        )
        for command, service_manager in commands_managers:
            if client.run(command.split()).returncode == 0:
                _SERVICE_MANAGERS[hostname] = service_manager
                return service_manager
        raise exceptions.NoKnownServiceManagerError(
            'Unable to determine the service manager used by {}. It does not '
            'appear to be any of {}.'
            .format(hostname, {manager for _, manager in commands_managers})
        )

    @contextlib.contextmanager
    def _disable_selinux(self):
        """Context manager to temporary disable SELinux."""
        if self._on_jenkins:
            self._client.run(self._sudo + ('setenforce', '0'))
        yield
        if self._on_jenkins:
            self._client.run(self._sudo + ('setenforce', '1'))

    def start(self, services):
        """Start the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == 'sysv':
            with self._disable_selinux():
                return self._start_sysv(services)
        elif self._svc_mgr == 'systemd':
            return self._start_systemd(services)
        else:
            raise NotImplementedError(
                'Service manager not supported: {}'.format(self._svc_mgr)
            )

    def _start_sysv(self, services):
        return tuple((
            self._client.run(self._sudo + ('service', service, 'start'))
            for service in services
        ))

    def _start_systemd(self, services):
        cmd = self._sudo + ('systemctl', 'start') + tuple(services)
        return (self._client.run(cmd),)

    def stop(self, services):
        """Stop the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == 'sysv':
            with self._disable_selinux():
                return self._stop_sysv(services)
        elif self._svc_mgr == 'systemd':
            return self._stop_systemd(services)
        else:
            raise NotImplementedError(
                'Service manager not supported: {}'.format(self._svc_mgr)
            )

    def _stop_sysv(self, services):
        return tuple((
            self._client.run(self._sudo + ('service', service, 'stop'))
            for service in services
        ))

    def _stop_systemd(self, services):
        cmd = self._sudo + ('systemctl', 'stop') + tuple(services)
        return (self._client.run(cmd),)


class PackageManager(object):
    """A package manager on a system.

    Each instance of this class represents the package manager on a system. An
    example may help to clarify this idea:

    >>> from pulp_smash import cli, config
    >>> pkg_mgr = cli.PackageManager(config.get_config())
    >>> completed_process = pkg_mgr.install('vim')
    >>> completed_process = pkg_mgr.uninstall('vim')

    In the example above, the ``pkg_mgr`` object represents the package manager
    on the host referenced by :func:`pulp_smash.config.get_config`.

    Upon instantiation, a :class:`PackageManager` object talks to its target
    system and uses simple heuristics to determine which package manager is
    used. As a result, it's possible to manage packages on heterogeneous
    systems with homogeneous commands.

    Upon instantiation, a :class:`PackageManager` object also talks to its
    target system and determines whether it is running as root. If not root,
    all commands are prefixed with "sudo". Please ensure that Pulp Smash can
    either execute commands as root or can successfully execute ``sudo``. You
    may need to edit your ``~/.ssh/config`` file.

    :param pulp_smash.config.ServerConfig cfg: Information about the target
        system.
    :raises pulp_smash.exceptions.NoKnownPackageManagerError: If unable to find
        any package manager on the target system.
    """

    def __init__(self, cfg):
        """Initialize a new object."""
        self._client = Client(cfg)
        self._sudo = () if _is_root(cfg) else ('sudo',)
        self._pkg_mgr = self._get_package_manager(cfg)

    @staticmethod
    def _get_package_manager(cfg):
        """Talk to the target system and determine the package manager.

        Return "dnf" or "yum" if the package manager appears to be one of
        those. Raise an exception otherwise.
        """
        hostname = _get_hostname(cfg.base_url)
        try:
            return _PACKAGE_MANAGERS[hostname]
        except KeyError:
            pass

        client = Client(cfg, echo_handler)
        commands_managers = (
            (('which', 'dnf'), 'dnf'),
            (('which', 'yum'), 'yum'),
        )
        for cmd, pkg_mgr in commands_managers:
            if client.run(cmd).returncode == 0:
                _PACKAGE_MANAGERS[hostname] = pkg_mgr
                return pkg_mgr
        raise exceptions.NoKnownPackageManagerError(
            'Unable to determine the package manager used by {}. It does not '
            'appear to be any of {}.'
            .format(hostname, {pkg_mgr for _, pkg_mgr in commands_managers})
        )

    def install(self, *args):
        """Install the named packages.

        :rtype: pulp_smash.cli.CompletedProcess
        """
        if self._pkg_mgr == 'dnf':
            cmd = self._sudo + ('dnf', '-y', 'install') + tuple(args)
        elif self._pkg_mgr == 'yum':
            cmd = self._sudo + ('yum', '-y', 'install') + tuple(args)
        else:
            cmd = None
        assert cmd is not None
        return self._client.run(cmd)

    def uninstall(self, *args):
        """Uninstall the named packages.

        :rtype: pulp_smash.cli.CompletedProcess
        """
        if self._pkg_mgr == 'dnf':
            cmd = self._sudo + ('dnf', '-y', 'remove') + tuple(args)
        elif self._pkg_mgr == 'yum':
            cmd = self._sudo + ('yum', '-y', 'remove') + tuple(args)
        else:
            cmd = None
        assert cmd is not None
        return self._client.run(cmd)

    def upgrade(self, *args):
        """Upgrade the named packages.

        :rtype: pulp_smash.cli.CompletedProcess
        """
        if self._pkg_mgr == 'dnf':
            cmd = self._sudo + ('dnf', '-y', 'upgrade') + tuple(args)
        elif self._pkg_mgr == 'yum':
            cmd = self._sudo + ('yum', '-y', 'update') + tuple(args)
        else:
            cmd = None
        assert cmd is not None
        return self._client.run(cmd)
