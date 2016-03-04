# coding=utf-8
"""Test the API's schedule functionality for repository `syncronization`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true.

.. _syncronization:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/sync.html#scheduling-a-sync
"""

from __future__ import unicode_literals

import time
try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo


class CreateSuccessTestCase(utils.BaseAPITestCase):
    """Establish that we can create a schedule to sync the repository."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repo with a valid feed, create a schedule to sync it.

        Do the following:
        1. Create a repository with a valid feed
        2. Schedule sync to run every 30 seconds
        """
        super(CreateSuccessTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)

        # Create a repo with a valid feed
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])

        # Schedule a sync to run every 30 seconds
        scheduling_url = '/'.join([
            'importers', body['importer_type_id'], 'schedules/sync/'
        ])
        cls.response = client.post(
            urljoin(repo['_href'], scheduling_url),
            {'schedule': 'PT30S'}
        )

    def test_status_code(self):
        """Assert the response has an HTTP 201 status code."""
        self.assertEqual(self.response.status_code, 201)

    def test_count_enabled(self):
        """Validate the ``total_run_count`` and ``enabled`` attributes."""
        attrs = self.response.json()
        self.assertEqual(attrs.get('total_run_count'), 0)
        self.assertTrue(attrs.get('enabled'))


class CreateFailureTestCase(utils.BaseAPITestCase):
    """Establish that schedules are not created in `documented scenarios`_.

    .. _documented scenarios:
        https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/sync.html#scheduling-a-sync
    """

    @classmethod
    def setUpClass(cls):
        """Create several schedules.

        Each schedule is created to test a different failure scenario.
        """
        super(CreateFailureTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)

        # Create a repo with a valid feed
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])

        client.response_handler = api.echo_handler
        cls.bodies = (
            {'schedule': None},  # 400
            {'unknown': 'parameter', 'schedule': 'PT30S'},  # 400
            ['Incorrect data type'],  # 400
            {'missing_required_keys': 'schedule'},  # 400
            {'schedule': 'PT30S'},  # tests incorrect importer in url, 404
            {'schedule': 'PT30S'},  # tests incorrect repo in url, 404
        )
        scheduling_url = '/'.join([
            'importers', body['importer_type_id'], 'schedules/sync/'
        ])
        bad_importer_url = '/'.join([
            'importers', utils.uuid4(), 'schedules/sync/'
        ])
        bad_repo_path = '/'.join([REPOSITORY_PATH, utils.uuid4()])
        cls.paths = (
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], bad_importer_url),
            urljoin(bad_repo_path, scheduling_url)
        )
        cls.status_codes = (400, 400, 400, 400, 404, 404)
        cls.responses = [
            client.post(path, req_body) for path, req_body in zip(
                cls.paths, cls.bodies)
        ]

    def test_status_code(self):
        """Assert that each response has the expected HTTP status code."""
        for body, response, status_code in zip(
                self.bodies, self.responses, self.status_codes):
            with self.subTest(body=body):
                self.assertEqual(response.status_code, status_code)


class ReadUpdateDeleteTestCase(utils.BaseAPITestCase):
    """Establish that we can `read`_, `update`_ and `delete`_ schedules.

    This test case assumes the assertions in :class:`CreateSuccessTestCase`
    hold true.

    .. _read:
        https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/sync.html#listing-a-single-scheduled-sync
    .. _update:
        https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/sync.html#updating-a-scheduled-sync
    .. _delete:
        https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/sync.html#deleting-a-scheduled-sync
    """

    @classmethod
    def setUpClass(cls):
        """Create three schedules and read, update and delete them."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)

        # Create a repo with a valid feed
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Create schedules
        scheduling_url = '/'.join([
            'importers', body['importer_type_id'], 'schedules/sync/'
        ])
        scheduling_path = urljoin(repo['_href'], scheduling_url)
        cls.schedules = tuple((
            client.post(scheduling_path, {'schedule': 'PT30S'})
            for _ in range(3)
        ))
        cls.responses = {}
        client.response_handler = api.safe_handler

        # Attributes that may be changed after creation
        cls.mutable_attrs = [
            'consecutive_failures', 'last_run_at', 'last_updated', 'next_run',
            'first_run', 'remaining_runs', 'total_run_count'
        ]

        # Read the first schedule
        cls.responses['read_one'] = client.get(cls.schedules[0]['_href'])

        # Read all schedules for the repo
        cls.responses['read_many'] = client.get(scheduling_path)

        # Update the second schedule
        cls.update_body = {'schedule': 'PT1M'}
        cls.responses['update'] = client.put(
            cls.schedules[1]['_href'], cls.update_body
        )

        # Delete the third schedule
        cls.responses['delete'] = client.delete(cls.schedules[2]['_href'])

    def test_status_code(self):
        """Assert each response has a correct HTTP status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 200)

    def test_read_one(self):
        """Assert the "read_one" response contains the correct attributes."""
        attrs = self.responses['read_one'].json()
        self.assertEqual(set(self.schedules[0]), set(attrs))
        attrs = {key: attrs[key] for key in attrs
                 if key not in self.mutable_attrs}
        for key in attrs:
            with self.subTest(key=key):
                self.assertEqual(self.schedules[0][key], attrs[key])

    def test_read_many(self):
        """Assert the "read_many" response body contains all schedules."""
        attrs = self.responses['read_many'].json()
        self.assertEqual(len(attrs), 3)
        expected_hrefs = {schedule['_href'] for schedule in self.schedules}
        read_hrefs = {schedule['_href'] for schedule in attrs}
        self.assertEqual(expected_hrefs, read_hrefs)

    def test_update(self):
        """Assert the "update" response body has the correct attributes."""
        attrs = self.responses['update'].json()
        self.assertEqual(set(self.schedules[1]), set(attrs))
        for key in self.update_body:
            with self.subTest(key=key):
                self.assertEqual(self.update_body[key], attrs[key])
        attrs = {key: attrs[key] for key in attrs
                 if key not in self.mutable_attrs + self.update_body.keys()}
        for key in attrs:
            with self.subTest(key=key):
                self.assertEqual(self.schedules[1][key], attrs[key])


class ScheduledSyncTestCase(utils.BaseAPITestCase):
    """Establish that sync runs according to the specified schedule.

    This test case assumes the assertions in :class:`CreateSuccessTestCase`
    and :class:`ReadUpdateDeleteTestCase` hold true.
    """

    @classmethod
    def setUpClass(cls):
        """Create a schedule to sync the repo, verify the ``total_run_count``.

        Do the following:
        1. Create a repository with a valid feed
        2. Schedule sync to run every 30 seconds
        3. Wait for 40 seconds and read the schedule to get the number of
        "sync" runs.
        """
        super(ScheduledSyncTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)

        # Create a repo with a valid feed
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Schedule a sync to run every 30 seconds
        scheduling_url = '/'.join([
            'importers', body['importer_type_id'], 'schedules/sync/'
        ])
        schedule_path = urljoin(repo['_href'], scheduling_url)
        schedule = client.post(schedule_path, {'schedule': 'PT30S'})

        # Wait for sync to run
        time.sleep(40)

        # Read the schedule
        cls.response = client.get(schedule['_href'])

    def test_scheduled_sync(self):
        """Assert the sync ran successfully twice in the past 40 seconds."""
        self.assertEqual(self.response['total_run_count'], 2)
        self.assertEqual(self.response['consecutive_failures'], 0)
