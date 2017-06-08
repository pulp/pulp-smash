# coding=utf-8
"""Tests for publishing with the ``force_full`` parameter set.

When a repository is published, Pulp checks to see if certain steps can be
skipped. For example, if one publishes a repository twice in a row, the second
publish is a no-op, as nothing needs to be done. As of Pulp 2.9, clients can
tell Pulp to perform a "full" publish. When this is done, Pulp executes all
publication steps, even steps that normally would be skipped.

This module tests Pulp's handling of "full" publishes.
"""
from packaging.version import Version

from pulp_smash import api, selectors, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_SIGNED_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class ForceFullTestCase(utils.BaseAPITestCase):
    """Test the ``force_full`` option.

    Repeatedly publish a repository. Set the ``force_full`` option to various
    values, and try omitting it too.
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository."""
        super(ForceFullTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo)
        cls.repo = client.get(repo['_href'], params={'details': True})

    def get_step(self, steps, step_type):
        """Return the task step with the given ``step_type``.

        :param steps: A list of dicts, as can be accessed by
            ``call_report_task['result']['details']``.
        :param step_type: The ``step_type`` of a particular step, such as
            ``save_tar``.
        :returns: The matching step.
        :raises: An assertion error if exactly one match is not found.
        """
        matching_steps = [
            step for step in steps if step['step_type'] == step_type
        ]
        self.assertEqual(len(matching_steps), 1, (steps, step_type))
        return matching_steps[0]

    def test_01_force_full_false(self):
        """Publish the repository and set ``force_full`` to false.

        A full publish should occur.
        """
        call_report = utils.publish_repo(self.cfg, self.repo, {
            'id': self.repo['distributors'][0]['id'],
            'override_config': {'force_full': False}
        }).json()
        last_task = next(api.poll_spawned_tasks(self.cfg, call_report))
        task_steps = last_task['result']['details']
        step = self.get_step(task_steps, 'rpms')
        self.assertGreater(step['num_processed'], 0, step)

    def test_02_force_full_omit(self):
        """Publish the repository and omit ``force_full``.

        A fast-forward publish should occur. This test targets `Pulp #1966`_.

        .. _Pulp #1966: https://pulp.plan.io/issues/1966
        """
        if (self.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1966, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/1966')
        call_report = utils.publish_repo(self.cfg, self.repo).json()
        last_task = next(api.poll_spawned_tasks(self.cfg, call_report))
        task_steps = last_task['result']['details']
        step = self.get_step(task_steps, 'rpms')
        self.assertEqual(step['num_processed'], 0, step)

    def test_03_force_full_true(self):
        """Publish the repository and set ``force_full`` to true.

        A full publish should occur. The "force" publish feature was introduced
        in Pulp 2.9, and as such, this test will skip when run against an older
        version of Pulp. See `Pulp #1938`_.

        .. _Pulp #1938: https://pulp.plan.io/issues/1938
        """
        if self.cfg.version < Version('2.9'):
            self.skipTest(
                'This test requires Pulp 2.9. See: '
                'https://pulp.plan.io/issues/1938'
            )
        call_report = utils.publish_repo(self.cfg, self.repo, {
            'id': self.repo['distributors'][0]['id'],
            'override_config': {'force_full': True}
        }).json()
        last_task = next(api.poll_spawned_tasks(self.cfg, call_report))
        task_steps = last_task['result']['details']
        step = self.get_step(task_steps, 'rpms')
        self.assertGreater(step['num_processed'], 0, step)
