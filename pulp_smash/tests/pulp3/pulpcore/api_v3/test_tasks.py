# coding=utf-8
"""Verify that operations can be performed over Tasks."""
import unittest

from pulp_smash import api, config, utils
from pulp_smash.tests.pulp3.constants import REPO_PATH, TASKS_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import get_auth
from pulp_smash.tests.pulp3.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class TasksTestCase(unittest.TestCase):
    """Perform different operations over tasks."""

    def test_all(self):
        """Perform different operation over tasks.

        Do the following:

        1. Create and partially update a repository.
        2. List current tasks.
        3. Read a specific task.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.code_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo()).json()
        self.addCleanup(client.delete, repo['_href'])
        attrs = {'description': utils.uuid4()}
        response = client.patch(repo['_href'], attrs).json()

        with self.subTest('list tasks'):
            client.get(TASKS_PATH)

        with self.subTest('read a task'):
            client.get(response[0]['_href'])
