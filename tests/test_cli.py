# coding=utf-8
"""Unit tests for :mod:`pulp_smash.cli`."""
import socket
import unittest
from unittest import mock

from plumbum.machines.local import LocalMachine

from pulp_smash import cli, config, exceptions, utils
from pulp_smash.exceptions import NoKnownPackageManagerError


class EchoHandlerTestCase(unittest.TestCase):
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


class CodeHandlerTestCase(unittest.TestCase):
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


class CompletedProcessTestCase(unittest.TestCase):
    """Tests for :class:`pulp_smash.cli.CompletedProcess`."""

    def setUp(self):
        """Generate kwargs that can be used to instantiate a completed proc."""
        self.kwargs = {
            key: utils.uuid4()
            for key in {"args", "returncode", "stdout", "stderr"}
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
        self.kwargs["returncode"] = 0
        completed_proc = cli.CompletedProcess(**self.kwargs)
        self.assertIsNone(completed_proc.check_returncode())

    def test_check_returncode_nonzero(self):
        """Call ``check_returncode`` when ``returncode`` is not zero."""
        self.kwargs["returncode"] = 1
        completed_proc = cli.CompletedProcess(**self.kwargs)
        with self.assertRaises(exceptions.CalledProcessError):
            completed_proc.check_returncode()

    def test_can_eval(self):
        """Assert ``__repr__()`` can be parsed by ``eval()``."""
        string = repr(cli.CompletedProcess(**self.kwargs))
        from pulp_smash.cli import (
            CompletedProcess,
        )  # pylint:disable=unused-import,unused-variable

        # pylint:disable=eval-used
        self.assertEqual(string, repr(eval(string)))


class ClientTestCase(unittest.TestCase):
    """Tests for :class:`pulp_smash.cli.Client`."""

    def test_explicit_local_transport(self):
        """Assert it is possible to explicitly ask for a "local" transport."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(
                    hostname=utils.uuid4(),
                    roles={"pulp cli": {}, "shell": {"transport": "local"}},
                )
            ]
        )
        self.assertIsInstance(cli.Client(cfg).machine, LocalMachine)

    def test_implicit_local_transport(self):
        """Assert it is possible to implicitly ask for a "local" transport."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(hostname=socket.getfqdn(), roles={"shell": {}})
            ]
        )
        self.assertIsInstance(cli.Client(cfg).machine, LocalMachine)

    def test_default_response_handler(self):
        """Assert the default response handler checks return codes."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(
                    hostname=utils.uuid4(),
                    roles={"pulp cli": {}, "shell": {"transport": "local"}},
                )
            ]
        )
        self.assertIs(cli.Client(cfg).response_handler, cli.code_handler)

    def test_explicit_response_handler(self):
        """Assert it is possible to explicitly set a response handler."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(
                    hostname=utils.uuid4(),
                    roles={"pulp cli": {}, "shell": {"transport": "local"}},
                )
            ]
        )
        handler = mock.Mock()
        self.assertIs(cli.Client(cfg, handler).response_handler, handler)

    def test_implicit_pulp_host(self):
        """Assert it is possible to implicitly target a pulp cli PulpHost."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(hostname=utils.uuid4(), roles={"shell": {}}),
                config.PulpHost(hostname=utils.uuid4(), roles={"shell": {}}),
            ]
        )
        with mock.patch("pulp_smash.cli.plumbum") as plumbum:
            machine = mock.Mock()
            plumbum.machines.SshMachine.return_value = machine
            self.assertEqual(cli.Client(cfg).machine, machine)
            plumbum.machines.SshMachine.assert_called_once_with(
                cfg.hosts[0].hostname
            )

    def test_explicit_pulp_host(self):
        """Assert it is possible to explicitly target a pulp cli PulpHost."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(
                    hostname=utils.uuid4(), roles={"pulp cli": {}}
                ),
                config.PulpHost(
                    hostname=utils.uuid4(), roles={"pulp cli": {}}
                ),
            ]
        )
        with mock.patch("pulp_smash.cli.plumbum") as plumbum:
            machine = mock.Mock()
            plumbum.machines.SshMachine.return_value = machine
            self.assertEqual(
                cli.Client(cfg, pulp_host=cfg.hosts[1]).machine, machine
            )
            plumbum.machines.SshMachine.assert_called_once_with(
                cfg.hosts[1].hostname
            )

    def test_run(self):
        """Test run commands."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(hostname=socket.getfqdn(), roles={"shell": {}})
            ]
        )
        client = cli.Client(cfg)
        with mock.patch.object(client, "machine") as machine:

            machine.__getitem__.return_value = machine
            machine.run.return_value = (0, "ok", None)

            result = client.run(("ls", "-la"))

            # Internal call is: `machine[args[0]].run(args[1:], **kwargs)`
            # So assert `machine['ls']` is called
            machine.__getitem__.assert_called_once_with("ls")
            # then `.run(('-la',), **kwargs)`
            machine.run.assert_called_once_with(("-la",), retcode=None)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "ok")
            self.assertIsNone(result.stderr)

    def test_run_as_sudo(self):
        """Test run commands as sudo."""
        cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(hostname=socket.getfqdn(), roles={"shell": {}})
            ]
        )
        client = cli.Client(cfg)
        with mock.patch.object(client, "machine") as machine:

            machine.__getitem__.return_value = machine
            machine.run.return_value = (0, "ok", None)

            result = client.run(("ls", "-la"), sudo=True)

            # Internal call is: `machine[args[0]].run(args[1:], **kwargs)`
            # So assert `machine['sudo']` is called
            machine.__getitem__.assert_called_once_with("sudo")
            # then `.run(('ls', '-la'), **kwargs)`
            machine.run.assert_called_once_with(("ls", "-la"), retcode=None)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "ok")
            self.assertIsNone(result.stderr)


class IsRootTestCase(unittest.TestCase):
    """Tests for :class:`pulp_smash.cli.is_root`."""

    def test_positive(self):
        """Test what happens when we are root on the target host."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.stdout = " 0 "
            self.assertTrue(cli.is_root(mock.MagicMock()))

    def test_negative(self):
        """Test what happens when we aren't root on the target host."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.stdout = " 1 "
            self.assertFalse(cli.is_root(mock.MagicMock()))


class PackageManagerTestCase(unittest.TestCase):
    """Tests for :class:`pulp_smash.cli.PackageManager`."""

    # pylint:disable=no-member
    # pylint:disable=protected-access
    # pylint:disable=cell-var-from-loop

    @classmethod
    def setUpClass(cls):
        """Set common cfg for all tests."""
        cls.cfg = _get_pulp_smash_config(
            hosts=[
                config.PulpHost(
                    hostname=socket.getfqdn(),
                    roles={"shell": {}, "api": {"scheme": "https"}},
                )
            ]
        )

    def test_raise_no_known_package_manager(self,):
        """Test if invalid package manager throws exception."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 1
            # `fpm` is a Fake Package Manager
            client.return_value.run.return_value.stdout = "fpm"
            pkr_mgr = cli.PackageManager(self.cfg)
            with self.assertRaises(NoKnownPackageManagerError):
                self.assertIn(pkr_mgr.name, ("yum", "dnf"))

    def test_raise_if_unsupported(self,):
        """Test if proper exception raises on raise_if_unsupported."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 1
            # `fpm` is a Fake Package Manager
            client.return_value.run.return_value.stdout = "fpm"

            # Should not raise error without raise_if_unsupported param
            cli.PackageManager(self.cfg)

            with self.assertRaises(RuntimeError):
                cli.PackageManager(self.cfg, (RuntimeError, "foo"))

            with self.assertRaises(RuntimeError):
                cli.PackageManager(self.cfg, [RuntimeError])

            with self.assertRaises(RuntimeError):
                pkr_mgr = cli.PackageManager(self.cfg)
                pkr_mgr.raise_if_unsupported(RuntimeError)

    def test_package_manager_name(self):
        """Test the property `name` returns the proper Package Manager."""
        for name in ("yum", "dnf"):
            pkr_mgr = cli.PackageManager(self.cfg)
            with mock.patch.object(
                pkr_mgr, "_get_package_manager", lambda *_, **__: name
            ):
                with self.subTest(name=name):
                    # asserts .name property gets the proper value
                    self.assertEqual(pkr_mgr.name, name)

    def test_install(self):
        """Test client is called with installation command."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 0
            client.return_value.run.return_value.stdout = "installed"
            pkr_mgr = cli.PackageManager(self.cfg)
            with mock.patch.object(
                pkr_mgr, "_get_package_manager", lambda *_, **__: "dnf"
            ):
                response = pkr_mgr.install("fake-package-42")
                self.assertEqual(response.stdout, "installed")
                pkr_mgr._client.run.assert_called_once_with(
                    ("dnf", "-y", "install", "fake-package-42"), sudo=True
                )

    def test_uninstall(self):
        """Test client is called with uninstallation command."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 0
            client.return_value.run.return_value.stdout = "uninstalled"
            pkr_mgr = cli.PackageManager(self.cfg)
            with mock.patch.object(
                pkr_mgr, "_get_package_manager", lambda *_, **__: "dnf"
            ):
                response = pkr_mgr.uninstall("fake-package-42")
                self.assertEqual(response.stdout, "uninstalled")
                pkr_mgr._client.run.assert_called_once_with(
                    ("dnf", "-y", "remove", "fake-package-42"), sudo=True
                )

    def test_upgrade(self):
        """Test client is called with upgrade command."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 0
            client.return_value.run.return_value.stdout = "updated"
            pkr_mgr = cli.PackageManager(self.cfg)
            with mock.patch.object(
                pkr_mgr, "_get_package_manager", lambda *_, **__: "dnf"
            ):
                response = pkr_mgr.upgrade("fake-package-42")
                self.assertEqual(response.stdout, "updated")
                pkr_mgr._client.run.assert_called_once_with(
                    ("dnf", "-y", "update", "fake-package-42"), sudo=True
                )

    def test_apply_erratum(self):
        """Test apply erratum is called for supported package managers."""
        with mock.patch.object(cli, "Client") as client:
            client.return_value.run.return_value.returncode = 0
            for name in ("yum", "dnf"):
                pkr_mgr = cli.PackageManager(self.cfg)
                with mock.patch.object(
                    pkr_mgr, "_get_package_manager", lambda *_, **__: name
                ), mock.patch.object(pkr_mgr, "_client"), mock.patch.object(
                    pkr_mgr, "_dnf_apply_erratum"
                ), mock.patch.object(
                    pkr_mgr, "_yum_apply_erratum"
                ):
                    pkr_mgr.apply_erratum("1234:4567")
                    method = getattr(
                        pkr_mgr, "_{0}_apply_erratum".format(pkr_mgr.name)
                    )
                    method.assert_called_once_with("1234:4567")


def _get_pulp_smash_config(hosts):
    """Return a config object with made-up attributes.

    :param hosts: Passed through to :data:`pulp_smash.config.PulpSmashConfig`.
    :rtype: pulp_smash.config.PulpSmashConfig
    """
    return config.PulpSmashConfig(
        pulp_auth=["admin", "admin"],
        pulp_version="1!0",
        pulp_selinux_enabled=True,
        hosts=hosts,
    )
