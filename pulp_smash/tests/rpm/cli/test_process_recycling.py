# coding=utf-8
"""Test Pulp's ability to recycle processes."""
import unittest

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import PULP_SERVICES, RPM_UNSIGNED_FEED_URL
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Conditionally skip this module, and execute ``pulp-admin login``."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


def restart_pulp(cfg):
    """Restart all of Pulp's services.

    Unlike :func:`pulp_smash.utils.reset_pulp`, do not reset the state of any
    of Pulp's services.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        deployment being targeted.
    """
    svc_mgr = cli.GlobalServiceManager(cfg)
    svc_mgr.stop(PULP_SERVICES)
    svc_mgr.start(PULP_SERVICES)


def get_pulp_worker_procs(cfg):
    """Use ``ps aux`` to get information about each Pulp worker process.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        deployment being targeted.
    :return: An iterable of strings, one per line of matching output.
    """
    cmd = ['ps', 'aux']
    if not utils.is_root(cfg):
        cmd.insert(0, 'sudo')
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

    1. Use ``ps`` to see how Pulp worker processes were invoked. None should
       have the ``--maxtasksperchild`` option set.
    2. Set ``PULP_MAX_TASKS_PER_CHILD`` and restart Pulp. Use ``ps`` to see how
       Pulp worker processes were invoked. Each should have the
       ``--maxtasksperchild`` option set as appropriate.
    3. Execute a sync and publish. No errors should be reported.
    4. Reset the ``PULP_MAX_TASKS_PER_CHILD`` option and restart Pulp.
       ``ps`` to see how Pulp worker processes were invoked. Each should have
       the ``--maxtasksperchild`` option set as appropriate.

    For more information, see `Pulp #2172 <https://pulp.plan.io/issues/2172>`_.
    """

    def test_all(self):
        """Test Pulp's handling of its ``PULP_MAX_TASKS_PER_CHILD`` setting."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(2172, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2172')
        set_opt = [
            'sed', '-i', '-e',
            's/.*PULP_MAX_TASKS_PER_CHILD=[0-9]*$/PULP_MAX_TASKS_PER_CHILD=2/',
            '/etc/default/pulp_workers'
        ]
        reset_opt = [
            'sed', '-i', '-e',
            's/^PULP_MAX_TASKS_PER_CHILD=2$/# PULP_MAX_TASKS_PER_CHILD=2/',
            '/etc/default/pulp_workers'
        ]
        if not utils.is_root(cfg):
            for cmd in (set_opt, reset_opt):
                cmd.insert(0, 'sudo')

        # Step 1
        for proc in get_pulp_worker_procs(cfg):
            self.assertNotIn('--maxtasksperchild=2', proc)

        # Step 2
        client = cli.Client(cfg)
        client.run(set_opt)
        self.addCleanup(client.run, reset_opt)
        restart_pulp(cfg)
        for proc in get_pulp_worker_procs(cfg):
            self.assertIn('--maxtasksperchild=2', proc)

        # Step 3
        repo_id = utils.uuid4()
        proc = client.run(
            'pulp-admin rpm repo create --repo-id {} --feed {}'
            .format(repo_id, RPM_UNSIGNED_FEED_URL).split()
        )
        self.addCleanup(
            client.run,
            'pulp-admin rpm repo delete --repo-id {}'.format(repo_id).split()
        )
        self.assertNotIn('Task Failed', proc.stdout)
        proc = client.run(
            'pulp-admin rpm repo sync run --repo-id {}'.format(repo_id).split()
        )
        self.assertNotIn('Task Failed', proc.stdout)

        # Step 4
        client.run(reset_opt)
        restart_pulp(cfg)
        for proc in get_pulp_worker_procs(cfg):
            self.assertNotIn('--maxtasksperchild=2', proc)
