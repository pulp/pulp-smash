# coding=utf-8
"""Test that operations can be performed over tasks."""
import unittest

from requests import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.api import P3_TASK_END_STATES
from pulp_smash.tests.pulp3.constants import REPO_PATH, TASKS_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_smash.tests.pulp3.utils import gen_repo, get_auth

_DYNAMIC_TASKS_ATTRS = ('finished_at',)
"""Task attributes that are dynamically set by Pulp, not set by a user."""


class TasksTestCase(unittest.TestCase, utils.SmokeTest):
    """Perform different operation over tasks.

    This test targets the following issues:

    * `Pulp #3144 <https://pulp.plan.io/issues/3144>`_
    * `Pulp #3527 <https://pulp.plan.io/issues/3527>`_
    * `Pulp Smash #754 <https://github.com/PulpQE/pulp-smash/issues/754>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = api.Client(config.get_config(), api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.task = {}

    def test_01_create_task(self):
        """Create a task."""
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        attrs = {'description': utils.uuid4()}
        response = self.client.patch(repo['_href'], attrs)
        self.task.update(self.client.get(response['_href']))

    @selectors.skip_if(bool, 'task', False)
    def test_02_read_href(self):
        """Read a task by its _href."""
        task = self.client.get(self.task['_href'])
        for key, val in self.task.items():
            if key in _DYNAMIC_TASKS_ATTRS:
                continue
            with self.subTest(key=key):
                self.assertEqual(task[key], val, task)

    @selectors.skip_if(bool, 'task', False)
    def test_02_read_invalid_worker(self):
        """Read a task using an invalid worker name."""
        with self.assertRaises(HTTPError):
            self.filter_tasks({'worker': utils.uuid4()})

    @selectors.skip_if(bool, 'task', False)
    def test_02_read_valid_worker(self):
        """Read a task using a valid worker name."""
        page = self.filter_tasks({'worker': self.task['worker']})
        self.assertNotEqual(len(page['results']), 0, page['results'])

    def test_02_read_invalid_date(self):
        """Read a task by an invalid date."""
        page = self.filter_tasks({
            'finished_at': utils.uuid4(),
            'started_at': utils.uuid4()})
        self.assertEqual(len(page['results']), 0, page['results'])

    @selectors.skip_if(bool, 'task', False)
    def test_02_read_valid_date(self):
        """Read a task by a valid date."""
        page = self.filter_tasks({'started_at': self.task['started_at']})
        self.assertGreaterEqual(len(page['results']), 1, page['results'])

    @selectors.skip_if(bool, 'task', False)
    def test_03_delete_tasks(self):
        """Delete a task."""
        # If this assertion fails, then either Pulp's tasking system or Pulp
        # Smash's code for interacting with the tasking system has a bug.
        self.assertIn(self.task['state'], P3_TASK_END_STATES)
        self.client.delete(self.task['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.task['_href'])

    def filter_tasks(self, criteria):
        """Filter tasks based on the provided criteria."""
        return self.client.get(TASKS_PATH, params=criteria)
