# coding=utf-8
"""Test Pulp's ability to recycle processes."""
import time
import unittest

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import RPM_UNSIGNED_FEED_URL
from pulp_smash.pulp2.constants import PULP_SERVICES
from pulp_smash.pulp2.utils import pulp_admin_login
from pulp_smash.tests.pulp2.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip this module, and execute ``pulp-admin login``."""
    set_up_module()
    pulp_admin_login(config.get_config())


def get_pulp_worker_procs(cfg):
    """Use ``ps aux`` to get information about each Pulp worker process.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        deployment being targeted.
    :return: An iterable of strings, one per line of matching output.
    """
    sudo = () if utils.is_root(cfg) else ('sudo',)
    cmd = sudo + ('ps', 'aux')
    return tuple((
        proc for proc in cli.Client(cfg).run(cmd).stdout.splitlines()
        if 'celery worker' in proc and 'resource_manager' not in proc
    ))


class MaxTasksPerChildTestCase(unittest.TestCase):
    """Test Pulp's handling of its ``PULP_MAX_TASKS_PER_CHILD`` setting.

    The ``PULP_MAX_TASKS_PER_CHILD`` setting controls how many tasks a worker
    process executes before being destroyed. Setting this option to a low
    value, like 2, ensures that processes don't have a chance to consume large
    amounts of memory.

    Test this feature by doing the following:

    1. Use ``ps`` to verify that no Pulp worker processes have the
       ``--maxtasksperchild`` option set.
    2. Set ``PULP_MAX_TASKS_PER_CHILD`` and restart Pulp. Use ``ps`` to verify
       that all Pulp worker processes were invoked with the
       ``--maxtasksperchild`` option.
    3. Execute a sync and publish. No errors should be reported.
    4. Unset the ``PULP_MAX_TASKS_PER_CHILD`` option and restart Pulp. Use
       ``ps`` to verify that no Pulp worker processes have the
       ``--maxtasksperchild`` option set.

    For more information, see `Pulp #2172 <https://pulp.plan.io/issues/2172>`_.
    """

    def test_all(self):
        """Test Pulp's handling of its ``PULP_MAX_TASKS_PER_CHILD`` setting."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(2172, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2172')
        pulp_3540_testable = selectors.bug_is_testable(3540, cfg.pulp_version)
        svc_mgr = cli.GlobalServiceManager(cfg)
        sudo = () if utils.is_root(cfg) else ('sudo',)
        set_cmd = sudo + (
            'sed', '-i', '-e',
            's/.*PULP_MAX_TASKS_PER_CHILD=[0-9]*$/PULP_MAX_TASKS_PER_CHILD=2/',
            '/etc/default/pulp_workers'
        )
        unset_cmd = sudo + (
            'sed', '-i', '-e',
            's/^PULP_MAX_TASKS_PER_CHILD=2$/# PULP_MAX_TASKS_PER_CHILD=2/',
            '/etc/default/pulp_workers'
        )
        procs_over_time = []

        # Step 1
        procs_over_time.append(get_pulp_worker_procs(cfg))
        for proc in procs_over_time[-1]:
            self.assertNotIn('--maxtasksperchild=2', proc, procs_over_time)

        # Step 2
        client = cli.Client(cfg)
        client.run(set_cmd)
        self.addCleanup(svc_mgr.restart, PULP_SERVICES)
        if not pulp_3540_testable:
            self.addCleanup(time.sleep, 30)
        self.addCleanup(client.run, unset_cmd)
        svc_mgr.restart(PULP_SERVICES)
        procs_over_time.append(get_pulp_worker_procs(cfg))
        for proc in procs_over_time[-1]:
            self.assertIn('--maxtasksperchild=2', proc, procs_over_time)

        # Step 3
        repo_id = utils.uuid4()
        proc = client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id,
            '--feed', RPM_UNSIGNED_FEED_URL
        ))
        self.addCleanup(client.run, (
            'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_id
        ))
        self.assertNotIn('Task Failed', proc.stdout)
        proc = client.run((
            'pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id', repo_id
        ))
        self.assertNotIn('Task Failed', proc.stdout)

        # Step 4
        self.doCleanups()
        procs_over_time.append(get_pulp_worker_procs(cfg))
        for proc in procs_over_time[-1]:
            self.assertNotIn('--maxtasksperchild=2', proc, procs_over_time)
