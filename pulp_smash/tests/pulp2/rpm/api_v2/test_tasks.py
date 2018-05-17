# coding=utf-8
"""Verify that operations can be performed over Tasks.

For information on tasks operations, see `REST API Task Management`_ and `Admin
Client Tasks`_.

.. _REST API Task Management:
    https://docs.pulpproject.org/dev-guide/integration/rest-api/tasks.html
.. _Admin Client Tasks:
    https://docs.pulpproject.org/user-guide/admin-client/tasks.html
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors
from pulp_smash.constants import RPM_SIGNED_FEED_URL
from pulp_smash.pulp2.constants import REPOSITORY_PATH, TASKS_PATH
from pulp_smash.pulp2.utils import publish_repo, sync_repo
from pulp_smash.tests.pulp2.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class TasksOperationsTestCase(unittest.TestCase):
    """Perform different operations over tasks.

    This test targets the following issues:

    * `Pulp Smash #108 <https://github.com/PulpQE/pulp-smash/issues/108>`_
    * `Pulp Smash #142 <https://github.com/PulpQE/pulp-smash/issues/142>`_
    * `Pulp issue #1418 <https://pulp.plan.io/issues/1418>`_
    * `Pulp issue #1483 <https://pulp.plan.io/issues/1483>`_
    * `Pulp issue #1664 <https://pulp.plan.io/issues/1664>`_
    """

    def test_all(self):
        """Perform different operation over tasks.

        Do the following:

        1. Create, sync and publish a repository.
        2. List current tasks.
        3. Search tasks.
        4. Polling a specific task progress.
        5. Delete finished tasks.
        6. Purge tasks.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(1418, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1418')
        if selectors.bug_is_untestable(1483, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1483')
        if selectors.bug_is_untestable(1664, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1664')

        # Create, sync and publish a repository.
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)

        with self.subTest('list tasks'):
            client.get(TASKS_PATH)

        with self.subTest('search tasks'):
            report = client.post(urljoin(TASKS_PATH, 'search/'), {
                'criteria': {'fields': [
                    'tags',
                    'task_id',
                    'state',
                    'start_time',
                    'finish_time'
                ]}
            })

        with self.subTest('poll task progress'):
            try:
                report
            except NameError:
                self.skipTest("Previous test failed, can't run this one.")
            client.post((urljoin(TASKS_PATH, report[0]['task_id'])))

        client.response_handler = api.safe_handler
        with self.subTest('delete (purge) finished tasks'):
            client.delete(TASKS_PATH, params={'state': 'finished'})

        with self.subTest('delete (purge) all tasks'):
            client.delete(TASKS_PATH, params={
                'state': ['finished', 'skipped', 'error'],
            })
