# coding=utf-8
"""Tests for the ``pulp-manage-db`` executable.

``pulp-manage-db`` should only run when :data:`REQUIRED_SERVICES` are running
and when :data:`CONFLICTING_SERVICES` are stopped. See:

* `Pulp #2186 <https://pulp.plan.io/issues/2186>`_
* `Pulp Smash #487 <https://github.com/PulpQE/pulp-smash/issues/487>`_
"""
import inspect
import unittest

from pulp_smash import cli, config, exceptions, selectors, utils

REQUIRED_SERVICES = frozenset(('mongod',))
"""If any of these services are stopped, ``pulp-manage-db`` will abort."""

CONFLICTING_SERVICES = frozenset((
    'pulp_celerybeat',
    'pulp_resource_manager',
    'pulp_workers',
))
"""If any of these services are running, ``pulp-manage-db`` will abort."""


def setUpModule():  # pylint:disable=invalid-name
    """Log in."""
    utils.pulp_admin_login(config.get_config())


def tearDownModule():  # pylint:disable=invalid-name
    """Reset Pulp, in case one of the test cases breaks Pulp."""
    utils.reset_pulp(config.get_config())


class BaseTestCase(unittest.TestCase):
    """An abstract base class for the test cases in this module."""

    @classmethod
    def setUpClass(cls):
        """Maybe skip this test case."""
        if inspect.getmro(cls)[0] == BaseTestCase:
            raise unittest.SkipTest('Abstract base class.')
        cls.cfg = config.get_config()
        if selectors.bug_is_untestable(2186, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2186')
        cls.cmd = () if utils.is_root(cls.cfg) else ('sudo',)
        cls.cmd += (
            'runuser', '--shell', '/bin/sh', '--command', 'pulp-manage-db',
            '-', 'apache'
        )

    def tearDown(self):
        """Start all of Pulp's services."""
        cli.GlobalServiceManager(config.get_config()).start(
            CONFLICTING_SERVICES.union(REQUIRED_SERVICES)
        )


class PositiveTestCase(BaseTestCase):
    """Assert ``pulp-manage-db`` runs when appropriate."""

    def test_conflicting_stopped(self):
        """Test with :data:`CONFLICTING_SERVICES` stopped."""
        cli.GlobalServiceManager(self.cfg).stop((
            'pulp_celerybeat',
            'pulp_resource_manager',
            'pulp_workers',
        ))
        cli.Client(self.cfg).run(self.cmd)


class NegativeTestCase(BaseTestCase):
    """Assert ``pulp-manage-db`` doesn't run when inappropriate."""

    def test_required_stopped(self):
        """Test with :data:`REQUIRED_SERVICES` stopped."""
        cli.GlobalServiceManager(self.cfg).stop(REQUIRED_SERVICES)
        self._do_test()

    def test_conflicting_running(self):
        """Test with :data:`CONFLICTING_SERVICES` running."""
        self._do_test()

    def test_celerybeat_running(self):
        """Test with ``pulp_celerybeat`` running."""
        cli.GlobalServiceManager(config.get_config()).stop((
            CONFLICTING_SERVICES.difference(('pulp_celerybeat',))
        ))
        self._do_test()

    def test_resource_manager_running(self):
        """Test with ``pulp_resource_manager`` running.

        This test targets `Pulp #2684 <https://pulp.plan.io/issues/2684>`_.
        """
        if selectors.bug_is_untestable(2684, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2684')
        cli.GlobalServiceManager(config.get_config()).stop((
            CONFLICTING_SERVICES.difference(('pulp_resource_manager',))
        ))
        self._do_test()

    def test_workers_running(self):
        """Test with ``pulp_workers`` running.

        This test targets `Pulp #2684 <https://pulp.plan.io/issues/2684>`_.
        """
        if selectors.bug_is_untestable(2684, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2684')
        cli.GlobalServiceManager(config.get_config()).stop((
            CONFLICTING_SERVICES.difference(('pulp_workers',))
        ))
        self._do_test()

    def _do_test(self):
        """Execute the common steps of each test method."""
        # The debugging message produced by this method when it fails is
        # disgusting to look at, but very useful. If you ever have to deal with
        # it, copy the string you want and print it in a Python interpreter.
        client = cli.Client(self.cfg, cli.echo_handler)
        procs = (client.run(self.cmd), client.run(('systemctl', 'status')))
        with self.assertRaises(exceptions.CalledProcessError, msg=procs):
            procs[0].check_returncode()
