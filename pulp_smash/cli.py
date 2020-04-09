# coding=utf-8
"""A client for working with Pulp hosts via their CLI."""
import collections
import contextlib
import json
import os
import socket
from abc import ABCMeta, abstractmethod
from functools import partialmethod
from urllib.parse import urlsplit, urlunsplit

import plumbum
from packaging.version import Version

from pulp_smash import exceptions
from pulp_smash.log import logger


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
        Client(cfg, pulp_host=pulp_host).run(("id", "-u")).stdout.strip()
    ) == "0"


def echo_handler(completed_proc):
    """Immediately return ``completed_proc``."""
    logger.debug("Process return code: %s", completed_proc.returncode)
    return completed_proc


def code_handler(completed_proc):
    """Check the process for a non-zero return code. Return the process.

    Check the return code by calling ``completed_proc.check_returncode()``.
    See: :meth:`pulp_smash.cli.CompletedProcess.check_returncode`.
    """
    completed_proc.check_returncode()
    logger.debug("Process return code: %s", completed_proc.returncode)
    return completed_proc


class CompletedProcess:
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
        str_kwargs = ", ".join(
            [
                "args={!r}".format(self.args),
                "returncode={!r}".format(self.returncode),
                "stdout={!r}".format(self.stdout),
                "stderr={!r}".format(self.stderr),
            ]
        )
        return "{}({})".format(type(self).__name__, str_kwargs)

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
                self.args, self.returncode, self.stdout, self.stderr
            )


class Client:  # pylint:disable=too-few-public-methods
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

    def __init__(
        self, cfg, response_handler=None, pulp_host=None, local=False
    ):
        """Initialize this object with needed instance attributes."""
        # How do we make requests?
        if not pulp_host:
            if cfg.pulp_version < Version("3"):
                pulp_host = cfg.get_hosts("pulp cli")[0]
            else:
                pulp_host = cfg.get_hosts("shell")[0]

        if local:
            pulp_host = collections.namedtuple("Host", "hostname roles")
            pulp_host.hostname = "localhost"
            pulp_host.roles = {"shell": {"transport": "local"}}

        self.pulp_host = pulp_host
        self.response_handler = response_handler or code_handler
        self.cfg = cfg

        self._is_root_cache = None
        self._machine = None
        self._transport = None
        self._podname = None
        logger.debug("New %s", self)

    def __str__(self):
        """Client str representation."""
        client_spec = {
            "response_handler": self.response_handler,
            "host": self.pulp_host,
            "cfg": repr(self.cfg),
        }
        return "<cli.Client(%s)>" % client_spec

    @property
    def transport(self):
        """Derive the transport protocol lazily."""
        if self._transport is None:
            self._transport = self.pulp_host.roles.get("shell", {}).get(
                "transport"
            )
            if self._transport is None:
                hostname = self.pulp_host.hostname
                self._transport = (
                    "local" if hostname == socket.getfqdn() else "ssh"
                )
        return self._transport

    @property
    def machine(self):
        """Initialize the plumbum machine lazily."""
        if self._machine is None:
            if self.transport == "local":
                self._machine = plumbum.machines.local
            elif self.transport == "kubectl":
                self._machine = plumbum.machines.local
                chain = (
                    self._machine["sudo"]["kubectl", "get", "pods"]
                    | self._machine["grep"][
                        "-E", "-o", r"pulp-api-(\w+)-(\w+)"
                    ]
                )
                self._podname = chain().replace("\n", "")
            elif self.transport == "podman":
                self._machine = plumbum.machines.local
                self._podname = self.pulp_host.roles.get("shell", {}).get(
                    "container", "pulp"
                )
            elif self.transport == "ssh":
                # The SshMachine is a wrapper around the host's "ssh" binary.
                # Thus, it uses ~/.ssh/config, ~/.ssh/known_hosts, etc.
                hostname = self.pulp_host.hostname
                self._machine = plumbum.machines.SshMachine(hostname)
            else:
                raise NotImplementedError(
                    "Transport ({}) is not implemented.".format(self.transport)
                )
            logger.debug("Initialized plumbum machine %s", self._machine)
        return self._machine

    @property
    def is_superuser(self):
        """Check if the current client is root.

        If the current client is in root mode it stores the status as a cache
        to avoid it to be called again.

        This property is named `is_supersuser` to avoid conflict with existing
        `is_root` function.
        """
        if self._is_root_cache is None:
            self._is_root_cache = is_root(self.cfg, self.pulp_host)
            if self._podname:
                self._is_root_cache = True
        logger.debug("Is Superuser: %s", self._is_root_cache)
        return self._is_root_cache

    def run(self, args, sudo=False, **kwargs):
        """Run a command and ``return self.response_handler(result)``.

        This method is a thin wrapper around Plumbum's `BaseCommand.run`_
        method, which is itself a thin wrapper around the standard library's
        `subprocess.Popen`_ class. See their documentation for detailed usage
        instructions. See :class:`pulp_smash.cli.Client` for a usage example.

        :param args: Any arguments to be passed to the process (a tuple).
        :param sudo: If the command should run as superuser (a boolean).
        :param kwargs: Extra named arguments passed to plumbumBaseCommand.run.

        .. _BaseCommand.run:
           http://plumbum.readthedocs.io/en/latest/api/commands.html#plumbum.commands.base.BaseCommand.run
        .. _subprocess.Popen:
           https://docs.python.org/3/library/subprocess.html#subprocess.Popen
        """
        # Let self.response_handler check return codes. See:
        # https://plumbum.readthedocs.io/en/latest/api/commands.html#plumbum.commands.base.BaseCommand.run
        kwargs.setdefault("retcode")
        logger.debug("Running %s cmd (sudo:%s) - %s", args, sudo, kwargs)

        # Some tests call run without instantiating the plumbum machine.
        if not self._machine:
            self.machine

        if self.transport == "kubectl":
            args = ("sudo", "kubectl", "exec", self._podname, "--") + tuple(
                args
            )
        elif self.transport == "podman":
            args = ("podman", "exec", "-it", self._podname) + tuple(args)

        if sudo and args[0] != "sudo" and not self.is_superuser:
            args = ("sudo",) + tuple(args)

        code, stdout, stderr = self.machine[args[0]].run(args[1:], **kwargs)
        completed_process = CompletedProcess(args, code, stdout, stderr)
        logger.debug("Finished %s command: %s", args, (code, stdout, stderr))
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
        self._on_jenkins = "JENKINS_HOME" in os.environ

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
            ("which systemctl", "systemd"),
            ("which service", "sysv"),
            ("test -x /sbin/service", "sysv"),
        )
        for command, service_manager in commands_managers:
            if client.run(command.split()).returncode == 0:
                _SERVICE_MANAGERS[pulp_host.hostname] = service_manager
                return service_manager
        raise exceptions.NoKnownServiceManagerError(
            "Unable to determine the service manager used by {}. It does not "
            "appear to be any of {}.".format(
                pulp_host.hostname,
                {manager for _, manager in commands_managers},
            )
        )

    @contextlib.contextmanager
    def _disable_selinux(self, client):
        """Context manager to temporary disable SELinux."""
        if self._on_jenkins:
            client.run(("setenforce", "0"), sudo=True)
        try:
            yield
        finally:
            if self._on_jenkins:
                client.run(("setenforce", "1"), sudo=True)

    @staticmethod
    def _start_sysv(client, services):
        return tuple(
            (
                client.run(("service", service, "start"), sudo=True)
                for service in services
            )
        )

    @staticmethod
    def _start_systemd(client, services):
        cmd = ("systemctl", "start") + tuple(services)
        return (client.run(cmd, sudo=True),)

    @staticmethod
    def _stop_sysv(client, services):
        return tuple(
            (
                client.run(("service", service, "stop"), sudo=True)
                for service in services
            )
        )

    @staticmethod
    def _stop_systemd(client, services):
        cmd = ("systemctl", "stop") + tuple(services)
        return (client.run(cmd, sudo=True),)

    @staticmethod
    def _restart_sysv(client, services):
        return tuple(
            (
                client.run(("service", service, "restart"), sudo=True)
                for service in services
            )
        )

    @staticmethod
    def _restart_systemd(client, services):
        cmd = ("systemctl", "restart") + tuple(services)
        return (client.run(cmd, sudo=True),)

    @staticmethod
    def _is_active_sysv(client, services):
        with contextlib.suppress(exceptions.CalledProcessError):
            return tuple(
                (
                    client.run(("service", service, "status"), sudo=True)
                    for service in services
                )
            )
        return False

    @staticmethod
    def _is_active_systemd(client, services):
        with contextlib.suppress(exceptions.CalledProcessError):
            cmd = ("systemctl", "is-active") + tuple(services)
            return (client.run(cmd, sudo=True),)
        return False

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

    @abstractmethod
    def is_active(self, services):
        """Check whether given services are active.

        :param services: A list or tuple of services to check.
        :return: boolean
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
    commands as root or can successfully execute "sudo". You may need to edit
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
        self._client_cache = {}

    def get_client(self, pulp_host, **kwargs):
        """Get an already instantiated client from cache."""
        return self._client_cache.setdefault(
            pulp_host.hostname,
            Client(self._cfg, pulp_host=pulp_host, **kwargs),
        )

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
                self._cfg.get_services(host.roles)
            )
            if intersection:
                client = self.get_client(pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                if svc_mgr == "sysv":
                    with self._disable_selinux(client):
                        result[host.hostname] = self._start_sysv(
                            client, services
                        )
                elif svc_mgr == "systemd":
                    result[host.hostname] = self._start_systemd(
                        client, services
                    )
                else:
                    raise NotImplementedError(
                        'Service manager "{}" not supported on "{}"'.format(
                            svc_mgr, host.hostname
                        )
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
                self._cfg.get_services(host.roles)
            )
            if intersection:
                client = self.get_client(pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                if svc_mgr == "sysv":
                    with self._disable_selinux(client):
                        result[host.hostname] = self._stop_sysv(
                            client, services
                        )
                elif svc_mgr == "systemd":
                    result[host.hostname] = self._stop_systemd(
                        client, services
                    )
                else:
                    raise NotImplementedError(
                        "Service manager not supported: {}".format(svc_mgr)
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
                self._cfg.get_services(host.roles)
            )
            if intersection:
                client = self.get_client(pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                if svc_mgr == "sysv":
                    with self._disable_selinux(client):
                        result[host.hostname] = self._restart_sysv(
                            client, services
                        )
                elif svc_mgr == "systemd":
                    result[host.hostname] = self._restart_systemd(
                        client, services
                    )
                else:
                    raise NotImplementedError(
                        "Service manager not supported: {}".format(svc_mgr)
                    )
        return result

    def is_active(self, services):
        """Check whether given services are active.

        :param services: A list or tuple of services to check.
        :return: boolean
        """
        services = set(services)
        result = {}
        for host in self._cfg.hosts:
            intersection = services.intersection(
                self._cfg.get_services(host.roles)
            )
            if intersection:
                client = self.get_client(pulp_host=host)
                svc_mgr = self._get_service_manager(self._cfg, host)
                if svc_mgr == "sysv":
                    with self._disable_selinux(client):
                        result[host.hostname] = self._is_active_sysv(
                            client, services
                        )
                elif svc_mgr == "systemd":
                    result[host.hostname] = self._is_active_systemd(
                        client, services
                    )
                else:
                    raise NotImplementedError(
                        "Service manager not supported: {}".format(svc_mgr)
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
    or can successfully execute "sudo". You may need to edit your
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
        """Initialize a new ServiceManager object."""
        super().__init__()
        self._client = Client(cfg, pulp_host=pulp_host)
        self._svc_mgr = self._get_service_manager(cfg, pulp_host)

    def start(self, services):
        """Start the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == "sysv":
            with self._disable_selinux(self._client):
                return self._start_sysv(self._client, services)
        elif self._svc_mgr == "systemd":
            return self._start_systemd(self._client, services)
        else:
            raise NotImplementedError(
                "Service manager not supported: {}".format(self._svc_mgr)
            )

    def stop(self, services):
        """Stop the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == "sysv":
            with self._disable_selinux(self._client):
                return self._stop_sysv(self._client, services)
        elif self._svc_mgr == "systemd":
            return self._stop_systemd(self._client, services)
        else:
            raise NotImplementedError(
                "Service manager not supported: {}".format(self._svc_mgr)
            )

    def restart(self, services):
        """Restart the given services.

        :param services: An iterable of service names.
        :return: An iterable of :class:`pulp_smash.cli.CompletedProcess`
            objects.
        """
        if self._svc_mgr == "sysv":
            with self._disable_selinux(self._client):
                return self._restart_sysv(self._client, services)
        elif self._svc_mgr == "systemd":
            return self._restart_systemd(self._client, services)
        else:
            raise NotImplementedError(
                "Service manager not supported: {}".format(self._svc_mgr)
            )

    def is_active(self, services):
        """Check whether given services are active.

        :param services: A list or tuple of services to check.
        :return: boolean
        """
        if self._svc_mgr == "sysv":
            with self._disable_selinux(self._client):
                return self._is_active_sysv(self._client, services)
        elif self._svc_mgr == "systemd":
            return self._is_active_systemd(self._client, services)
        else:
            raise NotImplementedError(
                "Service manager not supported: {}".format(self._svc_mgr)
            )


class PackageManager:
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
    or can successfully execute "sudo". You may need to edit your
    ``~/.ssh/config`` file.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the target
        host.
    :param tuple raise_if_unsupported: a tuple of Exception and optional
        string message to force raise_if_unsupported on initialization::

          pm = PackageManager(cfg, (unittest.SkipTest, 'Test requires yum'))
          # will raise and skip if unsupported package manager

        The optional is calling `pm.raise_if_unsupported` explicitly.
    """

    def __init__(self, cfg, raise_if_unsupported=None):
        """Initialize a new PackageManager object."""
        self._cfg = cfg
        self._client = Client(cfg)
        self._name = None
        if raise_if_unsupported is not None:
            self.raise_if_unsupported(*raise_if_unsupported)

    @property
    def name(self):
        """Return the name of the Package Manager."""
        if not self._name:
            self._name = self._get_package_manager(self._cfg)
        return self._name

    def raise_if_unsupported(self, exc, message="Unsupported package manager"):
        """Check if the package manager is supported else raise exc.

        Use case::

            pm = PackageManager(cfg)
            pm.raise_if_unsupported(unittest.SkipTest, 'Test requires yum/dnf')
            # will raise and skip if not yum or dnf
            pm.install('foobar')

        """
        try:
            self.name
        except exceptions.NoKnownPackageManagerError as e:
            logger.exception(e)
            raise exc(message)

    @staticmethod
    def _get_package_manager(cfg):
        """Talk to the target host and determine the package manager.

        Return "dnf" or "yum" if the package manager appears to be one of
        those.

        :raises pulp_smash.exceptions.NoKnownPackageManagerError: If unable to
        find any valid package manager on the target host.
        """
        hostname = urlsplit(cfg.get_base_url()).hostname
        with contextlib.suppress(KeyError):
            return _PACKAGE_MANAGERS[hostname]

        client = Client(cfg, echo_handler)
        commands_managers = (
            (("which", "dnf"), "dnf"),
            (("which", "yum"), "yum"),
        )
        for cmd, pkg_mgr in commands_managers:
            if client.run(cmd, sudo=True).returncode == 0:
                _PACKAGE_MANAGERS[hostname] = pkg_mgr
                return pkg_mgr
        raise exceptions.NoKnownPackageManagerError(
            "Unable to determine the package manager used by {}. It does not "
            "appear to be any of {}.".format(
                hostname, {pkg_mgr for _, pkg_mgr in commands_managers}
            )
        )

    def install(self, *args):
        """Install the named packages.

        :rtype: pulp_smash.cli.CompletedProcess
        """
        cmd = (self.name, "-y", "install") + tuple(args)
        return self._client.run(cmd, sudo=True)

    def uninstall(self, *args):
        """Uninstall the named packages.

        :rtype: pulp_smash.cli.CompletedProcess
        """
        cmd = (self.name, "-y", "remove") + tuple(args)
        return self._client.run(cmd, sudo=True)

    def upgrade(self, *args):
        """Upgrade the named packages.

        :rtype: pulp_smash.cli.CompletedProcess
        """
        cmd = (self.name, "-y", "update") + tuple(args)
        return self._client.run(cmd, sudo=True)

    def _dnf_apply_erratum(self, erratum):
        """Apply erratum using dnf."""
        lines = (
            self._client.run(
                ("dnf", "--quiet", "updateinfo", "list", erratum), sudo=True
            )
            .stdout.strip()
            .splitlines()
        )
        upgrade_targets = tuple((line.split()[2] for line in lines))
        return self.upgrade(upgrade_targets)

    def _yum_apply_erratum(self, erratum):
        """Apply erratum using yum."""
        upgrade_targets = ("--advisory", erratum)
        return self.upgrade(upgrade_targets)

    def apply_erratum(self, erratum):
        """Dispatch to proper _{self.name}_apply_erratum."""
        return getattr(self, "_{0}_apply_erratum".format(self.name))(erratum)


class RegistryClient:
    """A container registry client on test runner machine.

    Each instance of this class represents the registry client on a host. An
    example may help to clarify this idea:

    >>> from pulp_smash import cli, config
    >>> registry = cli.RegistryClient(config.get_config())
    >>> image = registry.pull('image_name')

    In the example above, the ``registry`` object represents the client
    on the host where pulp-smash is running the test cases.

    Upon instantiation, a :class:`RegistryClient` object talks to its target
    host and uses simple heuristics to determine which registry client is used.

    Upon instantiation, this object determines whether it is running as root.
    If not root, all commands are prefixed with "sudo".
    Please ensure that Pulp Smash can either execute commands as root
    or can successfully execute "sudo" on the localhost.

    .. note:: When running against a non-https registry the client config
        `insecure-registries` must be enabled.

    For docker it is located in `/etc/docker/daemon.json` and content is::

        {"insecure-registries": ["pulp_host:24816"]}

    For podman it is located in `/etc/containers/registries.conf` with::

        [registries.insecure]
        registries = ['pulp_host:24816']

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the target
        host.
    :param tuple raise_if_unsupported: a tuple of Exception and optional
        string message to force raise_if_unsupported on initialization::

          rc = RegistryClient(cfg, (unittest.SkipTest, 'Test requires podman'))
          # will raise and skip if unsupported package manager

        The optional is calling `rc.raise_if_unsupported` explicitly.
    :param pulp_host: The host where the Registry Client will run, by default
        it is set to None and then the same machine where tests are executed
        will be assumed.
    """

    def __init__(self, cfg, raise_if_unsupported=None, pulp_host=None):
        """Initialize a new RegistryClient object."""
        if pulp_host is None:
            # to comply with Client API
            smashrunner = collections.namedtuple("Host", "hostname roles")
            smashrunner.hostname = "localhost"
            smashrunner.roles = {"shell": {"transport": "local"}}
            self._pulp_host = smashrunner
        else:
            self._pulp_host = pulp_host

        self._cfg = cfg
        self._client = Client(cfg, pulp_host=self._pulp_host)
        self._name = None
        if raise_if_unsupported is not None:
            self.raise_if_unsupported(*raise_if_unsupported)

    @property
    def name(self):
        """Return the name of the Registry Client."""
        if not self._name:
            self._name = self._get_registry_client()
        return self._name

    def raise_if_unsupported(self, exc, message="Unsupported registry client"):
        """Check if the registry client is supported else raise exc.

        Use case::

            rc = RegistryClient(cfg)
            rc.raise_if_unsupported(unittest.SkipTest, 'Test requires podman')
            # will raise and skip if not podman or docker
            rc.pull('busybox')

        """
        try:
            self.name
        except exceptions.NoRegistryClientError as e:
            logger.exception(e)
            raise exc(message)

    def _get_registry_client(self):
        """Talk to the host and determine the registry client.

        Return "podman" or "docker" if the registry client appears to be one of
        those.

        :raises pulp_smash.exceptions.NoRegistryClientError: If unable to
        find any valid registry client on host.
        """
        client = Client(self._cfg, echo_handler, pulp_host=self._pulp_host)
        registry_clients = (
            (("which", "podman"), "podman"),
            (("which", "docker"), "docker"),
        )
        for cmd, registry_client in registry_clients:
            if client.run(cmd).returncode == 0:
                return registry_client
        raise exceptions.NoRegistryClientError(
            "Unable to determine the registry client used by {}. It does not "
            "appear to be any of {}.".format(
                self._pulp_host.hostname, {rc for _, rc in registry_clients}
            )
        )

    def _dispatch_command(self, command, *args):
        """Dispatch a command to the registry client."""
        # Scheme should not be part of image path, if so, remove it.
        if args and args[0].startswith(("http://", "https://")):
            args = list(args)
            args[0] = urlunsplit(urlsplit(args[0])._replace(scheme="")).strip(
                "//"
            )

        cmd = (self.name, command) + tuple(args)
        result = self._client.run(cmd, sudo=True)
        try:
            # most of client responses are JSONable
            return json.loads(result.stdout)
        except Exception:  # pylint:disable=broad-except
            # Python 3.4 has no specific error for json module
            return result

    pull = partialmethod(_dispatch_command, "pull")
    """Pulls image from registry."""
    login = partialmethod(_dispatch_command, "login")
    """Authenticate to a registry."""
    logout = partialmethod(_dispatch_command, "logout")
    """Logs out of a registry."""
    inspect = partialmethod(_dispatch_command, "inspect")
    """Inspect metadata for pulled image."""
    import_ = partialmethod(_dispatch_command, "import")
    """Import a container as a file in to the registry."""
    images = partialmethod(_dispatch_command, "images", "--format", "json")
    """List all pulled images."""
    rmi = partialmethod(_dispatch_command, "rmi")
    """removes pulled image."""
