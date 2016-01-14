# coding=utf-8
"""Tools for working with Pulp's CLI."""
from __future__ import unicode_literals

import socket
import subprocess
from sys import version_info
try:  # try Python 3 import first
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse  # pylint:disable=C0411,E0401

import plumbum


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

    This class mimics the ``subprocess.CompletedProcess`` class available in
    Python 3.5 and above. It has minor differences, such as requiring all
    constructor arguments. An instance of this class is returned by
    :meth:`pulp_smash.cli.Client.run`.

    All constructor arguments are stored as instance attributes.

    :param args: The list or str args passed to run().
    :param returncode: The exit code of the process, negative for signals.
    :param stdout: The standard output.
    :param stderr: The standard error.
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
        """Raise ``subprocess.CalledProcessError`` if exit code is non-zero."""
        if self.returncode:
            if version_info < (3, 5):  # pragma: no cover
                args = [self.returncode, self.args, self.stdout]
            else:  # pragma: no cover
                args = [self.returncode, self.args, self.stdout, self.stderr]
            raise subprocess.CalledProcessError(*args)


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

    .. _Plumbum: http://plumbum.readthedocs.org/en/latest/index.html
    """

    def __init__(self, server_config, response_handler=None):
        """Initialize this object with needed instance attributes."""
        # How do we make requests?
        hostname = _get_hostname(server_config.base_url)
        if server_config.cli_transport is None:
            transport = 'local' if hostname == socket.gethostname() else 'ssh'
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
           http://plumbum.readthedocs.org/en/latest/api/commands.html#plumbum.commands.base.BaseCommand.run
        .. _subprocess.Popen:
           https://docs.python.org/3/library/subprocess.html#subprocess.Popen
        """
        code, stdout, stderr = self.machine[args[0]].run(args[1:], **kwargs)
        completed_process = CompletedProcess(args, code, stdout, stderr)
        return self.response_handler(completed_process)
