# coding=utf-8
"""Unit tests for :mod:`pulp_smash.cli`."""
from __future__ import unicode_literals

import socket
import subprocess

import mock
import unittest2
from plumbum.machines.local import LocalMachine

from pulp_smash import cli, config, utils


class GetHostnameTestCase(unittest2.TestCase):
    """Tests for ``pulp_smash.cli._get_hostname``."""

    def test_parsing(self):
        """Assert the function extracts hostnames as shown in its docstring."""
        hostname = utils.uuid4()
        urlstrings = (
            '//' + hostname,
            'ftp://' + hostname,
            hostname + ':123',
            hostname,
        )
        outputs = [
            cli._get_hostname(urlstring)  # pylint:disable=protected-access
            for urlstring in urlstrings
        ]
        for urlstring, output in zip(urlstrings, outputs):
            with self.subTest(urlstring=urlstring):
                self.assertEqual(output, hostname)


class EchoHandlerTestCase(unittest2.TestCase):
    """Tests for :func:`pulp_smash.cli.echo_handler`."""

    @classmethod
    def setUpClass(cls):
        """Call the function under test, and record inputs and outputs."""
        cls.completed_proc = mock.Mock()
        cls.output = cli.echo_handler(cls.completed_proc)

    def test_input_returned(self):
        """Assert the passed-in ``completed_proc`` is returned."""
        self.assertIs(self.completed_proc, self.output)

    def test_check_returncode(self):
        """Assert ``completed_proc.check_returncode()`` is not called."""
        self.assertEqual(self.completed_proc.check_returncode.call_count, 0)


class CodeHandlerTestCase(unittest2.TestCase):
    """Tests for :func:`pulp_smash.cli.code_handler`."""

    @classmethod
    def setUpClass(cls):
        """Call the function under test, and record inputs and outputs."""
        cls.completed_proc = mock.Mock()
        cls.output = cli.code_handler(cls.completed_proc)

    def test_input_returned(self):
        """Assert the passed-in ``completed_proc`` is returned."""
        self.assertIs(self.completed_proc, self.output)

    def test_check_returncode(self):
        """Assert ``completed_proc.check_returncode()`` is not called."""
        self.assertEqual(self.completed_proc.check_returncode.call_count, 1)


class CompletedProcessTestCase(unittest2.TestCase):
    """Tests for :class:`pulp_smash.cli.CompletedProcess`."""

    def setUp(self):
        """Generate kwargs that can be used to instantiate a completed proc."""
        self.kwargs = {
            key: utils.uuid4()
            for key in {'args', 'returncode', 'stdout', 'stderr'}
        }

    def test_init(self):
        """Assert all constructor arguments are saved as instance attrs."""
        completed_proc = cli.CompletedProcess(**self.kwargs)
        for key, value in self.kwargs.items():
            with self.subTest(key=key):
                self.assertTrue(hasattr(completed_proc, key))
                self.assertEqual(getattr(completed_proc, key), value)

    def test_check_returncode_zero(self):
        """Call ``check_returncode`` when ``returncode`` is zero."""
        self.kwargs['returncode'] = 0
        completed_proc = cli.CompletedProcess(**self.kwargs)
        self.assertIsNone(completed_proc.check_returncode())

    def test_check_returncode_nonzero(self):
        """Call ``check_returncode`` when ``returncode`` is not zero."""
        self.kwargs['returncode'] = 1
        completed_proc = cli.CompletedProcess(**self.kwargs)
        with self.assertRaises(subprocess.CalledProcessError):
            completed_proc.check_returncode()

    def test_can_eval(self):
        """Assert ``__repr__()`` can be parsed by ``eval()``."""
        string = repr(cli.CompletedProcess(**self.kwargs))
        from pulp_smash.cli import CompletedProcess  # noqa
        # pylint:disable=eval-used
        self.assertEqual(string, repr(eval(string)))


class ClientTestCase(unittest2.TestCase):
    """Tests for :class:`pulp_smash.cli.Client`."""

    def test_explicit_local_transport(self):
        """Assert it is possible to explicitly ask for a "local" transport."""
        cfg = config.ServerConfig(utils.uuid4(), cli_transport='local')
        self.assertIsInstance(cli.Client(cfg).machine, LocalMachine)

    def test_implicit_local_transport(self):
        """Assert it is possible to implicitly ask for a "local" transport."""
        cfg = config.ServerConfig(socket.getfqdn())
        self.assertIsInstance(cli.Client(cfg).machine, LocalMachine)

    def test_default_response_handler(self):
        """Assert the default response handler checks return codes."""
        cfg = config.ServerConfig(utils.uuid4(), cli_transport='local')
        self.assertIs(cli.Client(cfg).response_handler, cli.code_handler)

    def test_explicit_response_handler(self):
        """Assert it is possible to explicitly set a response handler."""
        cfg = config.ServerConfig(utils.uuid4(), cli_transport='local')
        handler = mock.Mock()
        self.assertIs(cli.Client(cfg, handler).response_handler, handler)


class ServiceTestCase(unittest2.TestCase):
    """Tests for :class:`pulp_smash.cli.Service`."""

    @classmethod
    def setUpClass(cls):
        """Instantiate and save :class:`pulp_smash.cli.Service` objects.

        Give each object a different service manager (systemd, sysv, etc).
        """
        cls.services = []
        with mock.patch.object(cli.Service, '_get_prefix', return_value=()):
            with mock.patch.object(cli, 'Client'):
                for service_manager in ('systemd', 'sysv'):
                    with mock.patch.object(
                        cli.Service,
                        '_get_service_manager',
                        return_value=service_manager,
                    ):
                        service = cli.Service(mock.Mock(), mock.Mock())
                        cls.services.append(service)

    def test_command_builder(self):
        """Assert the ``_command_builder`` attribute is not ``None``.

        Tests of this sort aren't usually valuable. But in this case, it's
        fairly easy for a developer to simply make a mistake when editing the
        tightly related logic in ``__init__`` and ``_get_service_manager``.
        This may be a sign of bad design.
        """
        for i, service in enumerate(self.services):
            with self.subTest(i=i):
                # pylint:disable=protected-access
                self.assertIsNotNone(service._command_builder)
