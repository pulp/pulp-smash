# coding=utf-8
"""Verify that operations can be performed over Tasks.

For information on tasks operations, see `REST API Task Management`_
and `Admin Client Tasks`_.

.. _REST API Task Management:
    https://docs.pulpproject.org/dev-guide/integration/rest-api/tasks.html
.. _Admin Client Tasks:
    https://docs.pulpproject.org/user-guide/admin-client/tasks.html
"""

import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils, cli
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM_SIGNED_FEED_URL,
    TASKS_PATH,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo

from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


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
        """
        Perform different operation over tasks.

        Do the following:

        1. Create, sync and publish a repository.
        2. List current tasks.
        3. Search tasks.
        4. Polling a specific task progress.
        5. Delete finished tasks.
        6. Purge tasks.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(1418, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1418')
        if selectors.bug_is_untestable(1483, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1483')
        if selectors.bug_is_untestable(1664, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1664')

        client = api.Client(cfg, api.safe_handler)

        # Create, sync and publish a repository.
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body).json()
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True}).json()
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo)

        with self.subTest('listing tasks'):
            client.get(TASKS_PATH)

        with self.subTest('search tasks'):
            client.post(urljoin(TASKS_PATH, 'search/'), {
                'criteria':
                    {'fields': [
                        'tags',
                        'task_id',
                        'state',
                        'start_time',
                        'finish_time'
                    ]}
            })

        with self.subTest('polling task progress'):
            report = client.post(urljoin(TASKS_PATH, 'search/'), {
                'criteria':
                    {'fields': [
                        'tags',
                        'task_id',
                        'state',
                        'start_time',
                        'finish_time'
                    ]}
            }).json()
            client.post((urljoin(TASKS_PATH, report[0]['task_id'])))

        with self.subTest('delete finished tasks'):
            client.delete(TASKS_PATH, params={'state': 'finished'})

        cli_client = cli.Client(cfg, cli.code_handler)
        with self.subTest('purge all tasks'):
            cmd = ('pulp-admin', 'tasks', 'purge', '--all')
            cli_client.run(cmd)
