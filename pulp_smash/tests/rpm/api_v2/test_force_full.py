# coding=utf-8
"""Test pulp ability to run publish from scratch with 'force_full' parameter.

Following steps are executed in order to test correct functionality of
repository created with valid feed.

1. Create repository1 with valid feed, run sync
2. Create repository2 add distributor to it
3. Copy 3 units from repository1 to repository2
3. Publish repository2
3. Copy 3 units from repository1 to repository2
3. Publish repository2
3. Publish repository2 with force_full = true

4. Assert number of processed units from first publish == 3
4. Assert number of processed units from second publish == 3
4. Assert number of processed units from third publish == 6
"""
from __future__ import unicode_literals

import time

from pulp_smash import api, utils, selectors
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


class WaitForTasksTimeoutError(Exception):
    """Raised when wait_for_task method waited too long."""

    pass


def wait_for_tasks(client, cfg, tasks):
    """Wait until all tasks finish or raise exception."""
    task_ids = set()
    tasks_search = '/pulp/api/v2/tasks/search/'
    search_criteria = {'filters': {'state': {'$ne': 'running'}}}
    polls = 0
    for task in tasks:
        for spawned in task['spawned_tasks']:
            task_ids.add(spawned['task_id'])
    results = {}
    while task_ids:
        search_criteria['filters']['task_id'] = {'$in': list(task_ids)}
        finished_tasks = client.post(urljoin(cfg.base_url, tasks_search),
                                     {'criteria': search_criteria}).json()
        for task in finished_tasks:
            results[task['task_id']] = task
            task_ids -= set([task['task_id']])
        time.sleep(2)
        polls += 1
        if polls > 20:
            raise WaitForTasksTimeoutError()
    return results


def _copy_units(server_config, dest_repo_href, source_repo_id, units):
    """Copy units ``units`` from the repository ``repo1`` to ``repo2``.

    Return the JSON-decoded response body.
    """
    path = urljoin(dest_repo_href, 'actions/associate/')
    type_ids = list(set([unit['unit_type_id'] for unit in units]))
    units_ids = [unit['unit_id'] for unit in units]
    body = {'criteria': {'filters': {'unit': {'_id': {'$in': units_ids}}},
                         'type_ids': type_ids},
            'source_repo_id': source_repo_id}
    return api.Client(server_config).post(path, body).json()


class ForceFullTestCase(utils.BaseAPITestCase):
    """Test Forcefull feature."""

    @classmethod
    def setup_repo(cls, client):
        """Create repository and associate distributor with it."""
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body).json()

        # Add a distributor.
        distributor = client.post(
            urljoin(repo['_href'], 'distributors/'),
            gen_distributor(),
        ).json()
        return (repo, distributor)

    @classmethod
    def setUpClass(cls):
        """Create repository, associate, publish, associate, publish, publish.

        Following steps are executed:

        1. Create repository 1 with feed, sync and publish it.
        2. Create repository 2 with feed
        3. Copy 3 random units from repository 1 to repository 2
        4. Publish repository 2
        5. Copy 3 random units from repository 1 to repository 2
        6. Publish repository 2
        7. Publish repository 2 with force_full
        """
        super(ForceFullTestCase, cls).setUpClass()
        cls.responses = {}
        client = api.Client(cls.cfg)

        # Create repo 1
        repo1, _ = cls.setup_repo(client)
        cls.resources.add(repo1['_href'])  # mark for deletion

        # Sync repo 1
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo1['_href'])
        report = cls.responses['sync'].json()
        next(api.poll_spawned_tasks(cls.cfg, report))

        # Get all units
        cls.responses['repo1_units'] = client.post(
            urljoin(repo1['_href'], 'search/units/'),
            {'criteria': {'type_ids': ['rpm']}},
        ).json()

        # Create repo 2
        repo2, distributor2 = cls.setup_repo(client)
        cls.resources.add(repo2['_href'])  # mark for deletion

        rpm_units = cls.responses['repo1_units']

        # copy 3 random units
        units_to_copy = []
        for _ in range(0, 3):
            units_to_copy.append(rpm_units.pop(0))

        report = _copy_units(cls.cfg, repo2['_href'],
                             repo1['id'], units_to_copy)
        next(api.poll_spawned_tasks(cls.cfg, report))

        cls.responses['repo2_publish1'] = client.post(
            urljoin(repo2['_href'], 'actions/publish/'),
            {'id': distributor2['id']},
        ).json()
        next(api.poll_spawned_tasks(cls.cfg, cls.responses['repo2_publish1']))

        # copy another 3 random units
        units_to_copy2 = []
        for _ in range(0, 3):
            units_to_copy2.append(rpm_units.pop(0))

        report = _copy_units(cls.cfg, repo2['_href'],
                             repo1['id'], units_to_copy2)
        wait_for_tasks(client, cls.cfg, [report])

        cls.responses['repo2_publish2'] = client.post(
            urljoin(repo2['_href'], 'actions/publish/'),
            {'id': distributor2['id']},
        ).json()
        wait_for_tasks(client, cls.cfg, [cls.responses['repo2_publish2']])

        # publish with force_full
        cls.responses['repo2_publish_full'] = client.post(
            urljoin(repo2['_href'], 'actions/publish/'),
            {'id': distributor2['id'], 'force_full': True},
        ).json()

    def test_initial_publish(self):
        """Verify the number of processes units == 3."""
        report = self.responses['repo2_publish1']
        result = next(api.poll_spawned_tasks(self.cfg, report))
        details = result['result']['details']
        for step in details:
            if step['step_type'] == 'rpms':
                break
        else:
            step = None
        self.assertNotEqual(step, None)
        self.assertEqual(step['num_processed'], 3)

    def test_incremental_publish(self):
        """Verify the number of processes units == 3."""
        report = self.responses['repo2_publish2']
        result = next(api.poll_spawned_tasks(self.cfg, report))
        details = result['result']['details']
        for step in details:
            if step['step_type'] == 'rpms':
                break
        else:
            step = None
        self.assertNotEqual(step, None)
        self.assertEqual(step['num_processed'], 3)

    def test_force_full_publish(self):
        """Verify the number of processes units == 6."""
        if selectors.bug_is_testable(1158, self.cfg.version):
            report = self.responses['repo2_publish_full']
            result = next(api.poll_spawned_tasks(self.cfg, report))
            details = result['result']['details']
            for step in details:
                if step['step_type'] == 'rpms':
                    break
            else:
                step = None
            self.assertNotEqual(step, None)
            self.assertEqual(step['num_processed'], 6)
