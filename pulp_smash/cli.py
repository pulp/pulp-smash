# coding=utf-8
"""A client for working with Pulp hosts via their CLI."""
import contextlib
import os
import socket
from abc import ABCMeta, abstractmethod
from urllib.parse import urlsplit

import plumbum
from packaging.version import Version

from pulp_smash import exceptions


# A dict mapping hostnames to *nix service managers.
#
# For example: {'old.example.com': 'sysv', 'new.example.com', 'systemd'}
_SERVICE_MANAGERS = {}

# A dict mapping hostnames to *nix package managers.
#
# For example: {'old.example.com': 'yum', 'new.example.com', 'yum'}
_PACKAGE_MANAGERS = {}


def is_root(cfg, pulp_host=None):
    """Tell if we are root on the target host.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        application.
    :param pulp_smash.config.PulpHost pulp_host: A specific host to target,
        instead of the first host with the ``pulp cli`` role.
    :returns: Either ``True`` or ``False``.
    """
    return (
        Client(cfg, pulp_host=pulp_host)
        .run(('id', '-u'))
        .stdout
        .strip()) == '0'


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


class CompletedProcess():
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


class Client():  # pylint:disable=too-few-public-methods
    """A convenience object for working with a CLI.

    This class provides the ability to execute shell commands on either the
    local host or a remote host. Here is a typical usage example:

    >>> from pulp_smash import cli, config
    >>> client = cli.Client(config.PulpSmashConfig.load())
    >>> response = client.run(('echo', '-n', 'foo'))
    >>> response.returncode == 0
    True
    >>> response.stdout == 'foo'
    True
    >>> response.stderr == ''
    True

    Smartly chosen defaults make this example concise, but it's also quite
    flexible. For example, if a single Pulp application is deployed across
    several hosts, one can choose on which host commands are executed:

    >>> from pulp_smash import cli, config
    >>> cfg = config.PulpSmashConfig.load()
    >>> client = cli.Client(cfg, pulp_host=cfg.get_hosts('shell')[0])
    >>> response = client.run(('echo', '-n', 'foo'))

    You can customize how ``Client`` objects execute commands and handle
    responses by fiddling with the two public instance attributes:

    ``machine``
        A `Plumbum`_ machine. :meth:`run` delegates all command execution
        responsibilities to this object.
    ``response_handler``
        A callback function. Each time ``machine`` executes a command, the
        result is handed to this callback, and the callback's return value is
        handed to the user.

    If ``pulp_host.roles['shell']['transport']`` is ``'local'`` or ``'ssh``,
    ``machine`` will be set so that commands run locally or over SSH,
    respectively. If ``pulp_host.roles['shell']['transport']`` is ``None``,
    the constructor will guess how to set ``machine`` by comparing the hostname
    embedded in ``pulp_host.hostname`` against the current host's hostname.
    If they match, ``machine`` is set to execute commands locally; and vice
    versa.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about
        the host on which commands will be executed.
    :param response_handler: A callback function. Defaults to
        :func:`pulp_smash.cli.code_handler`.
    :param pulp_smash.config.PulpHost pulp_host: A specific host to target.
        Defaults to the first host with the ``pulp cli`` role when targeting
        Pulp 2, and the first host with the ``shell`` role when targeting Pulp
        3. If Pulp 3 gets a CLI, this latter default may change.

    .. _Plumbum: http://plumbum.readthedocs.io/en/latest/index.html
    """

    def __init__(self, cfg, response_handler=None, pulp_host=None):
        """Initialize this object with needed instance attributes."""
        # How do we make requests?
        if not pulp_host:
            if cfg.pulp_version < Version('3'):
                pulp_host = cfg.get_hosts('pulp cli')[0]
            else:
                pulp_host = cfg.get_hosts('shell')[0]
        self.pulp_host = pulp_host
        hostname = pulp_host.hostname
        transport = pulp_host.roles.get('shell', {}).get('transport')
        if transport is None:
            transport = 'local' if hostname == socket.getfqdn() else 'ssh'
        if transport == 'local':
            self.machine = plumbum.machines.local
        else:  # transport == 'ssh'
            # The SshMachine is a wrapper around the host's "ssh" binary.
            # Thus, it uses ~/.ssh/config, ~/.ssh/known_hosts, etc.
            self.machine = (
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


class BaseServiceManager(metaclass=ABCMeta):
    """A base service manager.

    Each subclass must implement the abstract methods to provide the service
    management on a single or multiple hosts.

    Subclasses should take advantage of the helper methods offered by this
    class in order to manage services and check the proper service manager
    software available on a host.

    This base class also offers a context manager to temporary disable SELinux.
    It is useful when managing services on hosts running RHEL 6 and earlier,
    which has SELinux issues when running on Jenkins.

    Make sure to call this class ``__init__`` method on the subclass
    ``__init__`` method to ensure the helper methods functionality.
    """

    def __init__(self):
        """Initialize variables expected by the helper methods."""
        self._on_jenkins = 'JENKINS_HOME' in os.environ

    @staticmethod
    def _get_service_manager(cfg, pulp_host):
        """Talk to the target host and determine the type of service manager.

        Return "systemd" or "sysv" if the service manager appears to be one of
        those. Raise an exception otherwise.
        """
        try:
            return _SERVICE_MANAGERS[pulp_host.hostname]
        except KeyError:
            pass

        client = Client(cfg, echo_handler, pulp_host=pulp_host)
        commands_managers = (
            ('which systemctl', 'systemd'),
            ('which service', 'sysv'),
            ('test -x /sbin/service', 'sysv'),
        )
        for command, service_manager in commands_managers:
            if client.run(command.split()).returncode == 0:
                _SERVICE_MANAGERS[pulp_host.hostname] = service_manager
                return service_manager
        raise exceptions.NoKnownServiceManagerError(
            'Unable to determine the service manager used by {}. It does not '
            'appear to be any of {}.'
            .format(
                pulp_host.hostname,
                {manager for _, manager in commands_managers}
            )
        )

    @contextlib.contextmanager
    def _disable_selinux(self, client, sudo=False):
        """Context manager to temporary disable SELinux."""
        sudo = ('sudo',) if sudo else ()
        if self._on_jenkins:
            client.run(sudo + ('setenforce', '0'))
        try:
            yield
        finally:
            if self._on_jenkins:
                client.run(sudo + ('setenforce', '1'))

    @staticmethod
    def _start_sysv(client, sudo, services):
        sudo = ('sudo',) if sudo else ()
        return tuple((
            client.run(sudo + ('service', service, 'start'))
            for service in services
        ))

    @staticmethod
    def _start_systemd(client, sudo, services):
        sudo = ('sudo',) if sudo else ()
        cmd = sudo + ('systemctl', 'start') + tuple(services)
        return (client.run(cmd),)

    @staticmethod
    def _stop_sysv(client, sudo, services):
        sudo = ('sudo',) if sudo else ()
        return tuple((
            client.run(sudo + ('service', service, 'stop'))
            for service in services
        ))

    @staticmethod
    def _stop_systemd(client, sudo, services):
        sudo = ('sudo',) if sudo else ()
        cmd = sudo + ('systemctl', 'stop') + tuple(services)
        return (client.run(cmd),)

    @staticmethod
    def _restart_sysv(client, sudo, services):
        sudo = ('sudo',) if sudo else ()
        return tuple((
            client.run(sudo + ('service', service, 'restart'))
            for service in services
        ))

    @staticmethod
    def _restart_systemd(client, sudo, services):
        sudo = ('sudo',) if sudo else ()
        cmd = sudo + ('systemctl', 'restart') + tuple(services)
        return (client.run(cmd),)

    @abstractmethod
    def start(self, services):
        """Start the given services.

        :param services: A list or tuple of services to be started.
        """
        pass

    @abstractmethod
    def stop(self, services):
        """Stop the given services.

        :param services: A list or tuple of services to be stopped.
        """
        pass

    @abstractmethod
    def restart(self, services):
        """Restart the given services.

        :param services: A list or tuple of services to be restarted.
        """
        pass


class GlobalServiceManager(BaseServiceManager):
    """A service manager that manages services on all Pulp hosts.

    Each instance of this class manages a single service. When a method like
    :meth:`start` is executed, it will start a service on all hosts that are
    declared as running that service. For example, imagine that the following
    is executed:

    >>> from pulp_smash import cli, config
    >>> cfg = config.get_config()
    >>> svc_mgr = cli.GlobalServiceManager(cfg)
    >>> svc_mgr.start(['httpd'])

    In this case, the service manager will iterate over all hosts in ``cfg``.
    For each host that is declared as fulfilling the ``api`` role, Apache
    (httpd) will be restarted.

    When asked to perform an action, this object may talk to each target host
    and determines whether it is running as root. If not root, all commands are
    prefixed with "sudo". Please ensure that Pulp Smash can either execute
    commands as root or can successfully execute ``sudo``. You may need to edit
    your ``~/.ssh/config`` file.

    For conceptual information on why both a
    :class:`pulp_smash.cli.ServiceManager` and a
    :class:`pulp_smash.cli.GlobalServiceManager` are necessary, see
    :class:`pulp_smash.config.PulpSmashConfig`.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        deployment.
    :raises pulp_smash.exceptions.NoKnownServiceManagerError: If unable to find
        any service manager on one of the target hosts.
    """

    def __init__(self, cfg):
        """Initialize a GlobalServiceManager object."""
        super().__init__()
        self._cfg = cfg
        self._is_root_cache = {}

    def _check_root(self, pulp_host):
        """Tell if we are root on the target host.

        Use the cache if the information is already available.
        """
        try:
            return self._is_root_cache[pulp_host.hostname]
        except KeyError:
            pass
        self._is_root_cache[pulp_host.hostname] = is_root(self._cfg, pulp_host)
        return self._is_root_cache[pulp_host.hostname]

    def start(self, services):
        """Start the services on every host that has the services.

        :param services: An iterable of service names.
        :return: A dict mapping the affected hosts' hostnames with a list of
            :class:`pulp_smash.cli.CompletedProcess` objects.
        """
        services = set(services)
        result = {}
        for host in self._cfg.hosts:
            intersection = services.intersection(
                self._cfg.get_services(host.roles))
            if intersection:
                client = Client(self._cfg, pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                sudo = not self._check_root(host)
                if svc_mgr == 'sysv':
                    with self._disable_selinux(client, sudo):
                        result[host.hostname] = self._start_sysv(
                            client, sudo, services)
                elif svc_mgr == 'systemd':
                    result[host.hostname] = self._start_systemd(
                        client, sudo, services)
                else:
                    raise NotImplementedError(
                        'Service manager "{}" not supported on "{}"'.format(
                            svc_mgr, host.hostname)
                    )
        return result

    def stop(self, services):
        """Stop the services on every host that has the services.

        :param services: An iterable of service names.
        :return: A dict mapping the affected hosts' hostnames with a list of
            :class:`pulp_smash.cli.CompletedProcess` objects.
        """
        services = set(services)
        result = {}
        for host in self._cfg.hosts:
            intersection = services.intersection(
                self._cfg.get_services(host.roles))
            if intersection:
                client = Client(self._cfg, pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                sudo = not self._check_root(host)
                if svc_mgr == 'sysv':
                    with self._disable_selinux(client, sudo):
                        result[host.hostname] = self._stop_sysv(
                            client, sudo, services)
                elif svc_mgr == 'systemd':
                    result[host.hostname] = self._stop_systemd(
                        client, sudo, services)
                else:
                    raise NotImplementedError(
                        'Service manager not supported: {}'.format(svc_mgr)
                    )
        return result

    def restart(self, services):
        """Restart the services on every host that has the services.

        :param services: An iterable of service names.
        :return: A dict mapping the affected hosts' hostnames with a list of
            :class:`pulp_smash.cli.CompletedProcess` objects.
        """
        services = set(services)
        result = {}
        for host in self._cfg.hosts:
            intersection = services.intersection(
                self._cfg.get_services(host.roles))
            if intersection:
                client = Client(self._cfg, pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                sudo = not self._check_root(host)
                if svc_mgr == 'sysv':
                    with self._disable_selinux(client, sudo):
                        result[host.hostname] = self._restart_sysv(
                            client, sudo, services)
                elif svc_mgr == 'systemd':
                    result[host.hostname] = self._restart_systemd(
                        client, sudo, services)
                else:
                    raise NotImplementedError(
                        'Service manager not supported: {}'.format(svc_mgr)
                    )
        return result


class ServiceManager(BaseServiceManager):
    """A service manager on a host.

    Each instance of this class represents the service manager on a host. An
    example may help to clarify this idea:

    >>> from pulp_smash import cli, config
    >>> cfg = config.get_config()
    >>> pulp_host = cfg.get_services(('api',))[0]
    >>> svc_mgr = cli.ServiceManager(cfg, pulp_host)
    >>> completed_process_list = svc_mgr.stop(['httpd'])
    >>> completed_process_list = svc_mgr.start(['httpd'])

    In the example above, ``svc_mgr`` represents the service manager (such as
    SysV or systemd) on a host. Upon instantiation, a :class:`ServiceManager`
    object talks to its target host and uses simple heuristics to determine
    which service manager is available. As a result, it's possible to manage
    services on heterogeneous hosts with homogeneous commands.

    Upon instantiation, this object talks to the target host and determines
    whether it is running as root. If not root, all commands are prefixed with
    "sudo". Please ensure that Pulp Smash can either execute commands as root
    or can successfully execute ``sudo``. You may need to edit your
    ``~/.ssh/config`` file.

    For conceptual information on why both a
    :class:`pulp_smash.cli.ServiceManager` and a
    :class:`pulp_smash.cli.GlobalServiceManager` are necessary, see
    :class:`pulp_smash.config.PulpSmashConfig`.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        application.
    :param pulp_smash.config.PulpHost pulp_host: The host to target.
    :raises pulp_smash.exceptions.NoKnownServiceManagerError: If unable to find
        any service manager on the target host.
    """

    def __init__(self, cfg, pulp_host):
        """Initialize a new object."""
        super().__init__()
        self._client = Client(cfg, pulp_host=pulp_host)
        self._sudo = not is_root(cfg, pulp_host)
        self._svc_mgr = self._get_service_manager(cfg, pulp_host)

    def start(self, services):
        """Start the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == 'sysv':
            with self._disable_selinux(self._client, self._sudo):
                return self._start_sysv(self._client, self._sudo, services)
        elif self._svc_mgr == 'systemd':
            return self._start_systemd(self._client, self._sudo, services)
        else:
            raise NotImplementedError(
                'Service manager not supported: {}'.format(self._svc_mgr)
            )

    def stop(self, services):
        """Stop the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == 'sysv':
            with self._disable_selinux(self._client, self._sudo):
                return self._stop_sysv(self._client, self._sudo, services)
        elif self._svc_mgr == 'systemd':
            return self._stop_systemd(self._client, self._sudo, services)
        else:
            raise NotImplementedError(
                'Service manager not supported: {}'.format(self._svc_mgr)
            )

    def restart(self, services):
        """Restart the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == 'sysv':
            with self._disable_selinux(self._client, self._sudo):
                return self._restart_sysv(self._client, self._sudo, services)
        elif self._svc_mgr == 'systemd':
            return self._restart_systemd(self._client, self._sudo, services)
        else:
            raise NotImplementedError(
                'Service manager not supported: {}'.format(self._svc_mgr)
            )


class PackageManager():
    """A package manager on a host.

    Each instance of this class represents the package manager on a host. An
    example may help to clarify this idea:

    >>> from pulp_smash import cli, config
    >>> pkg_mgr = cli.PackageManager(config.get_config())
    >>> completed_process = pkg_mgr.install('vim')
    >>> completed_process = pkg_mgr.uninstall('vim')

    In the example above, the ``pkg_mgr`` object represents the package manager
    on the host referenced by :func:`pulp_smash.config.get_config`.

    Upon instantiation, a :class:`PackageManager` object talks to its target
    host and uses simple heuristics to determine which package manager is used.
    As a result, it's possible to manage packages on heterogeneous host with
    homogeneous commands.

    Upon instantiation, this object talks to the target host and determines
    whether it is running as root. If not root, all commands are prefixed with
    "sudo". Please ensure that Pulp Smash can either execute commands as root
    or can successfully execute ``sudo``. You may need to edit your
    ``~/.ssh/config`` file.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the target
        host.
    :raises pulp_smash.exceptions.NoKnownPackageManagerError: If unable to find
        any package manager on the target host.
    """

    def __init__(self, cfg):
        """Initialize a new object."""
        self._client = Client(cfg)
        self._sudo = () if is_root(cfg) else ('sudo',)
        self._pkg_mgr = self._get_package_manager(cfg)

    @staticmethod
    def _get_package_manager(cfg):
        """Talk to the target host and determine the package manager.

        Return "dnf" or "yum" if the package manager appears to be one of
        those. Raise an exception otherwise.
        """
        hostname = urlsplit(cfg.get_base_url()).hostname
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
