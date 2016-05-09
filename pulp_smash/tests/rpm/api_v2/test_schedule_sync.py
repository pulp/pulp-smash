# coding=utf-8
"""Test the API's schedule functionality for repository `syncronization`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true.

.. _syncronization:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/sync.html#scheduling-a-sync
"""
from __future__ import unicode_literals

import time

from packaging.version import Version

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_MUTABLE_ATTRS = {
    'consecutive_failures',
    'last_run_at',
    'last_updated',
    'next_run',
    'first_run',
    'remaining_runs',
    'total_run_count',
}
# Pulp may, of its own accord, change these schedule attributes.

_SCHEDULE = {'schedule': 'PT30S'}
# Sync every 30 seconds.

_SCHEDULE_PATH = 'importers/{}/schedules/sync/'
# Usage: urljoin(repo['_href'], _SCHEDULE_PATH.format(importer_type_id))


# It's OK that this class has one method. It's an intentionally small class.
class CreateRepoMixin(object):  # pylint:disable=too-few-public-methods
    """Provide a method for creating a repository."""

    @classmethod
    def create_repo(cls):
        """Create a semi-random RPM repository with a valid RPM feed URL.

        Add this repository's href to ``cls.resources``. Return a two-tuple of
        ``(href, importer_type_id)``. This method requires a server config,
        ``cls.cfg``, and a set, ``cls.resources``.
        """
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        href = api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(href)
        return (href, body['importer_type_id'])


class CreateSuccessTestCase(CreateRepoMixin, utils.BaseAPITestCase):
    """Establish that we can create a schedule to sync the repository."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repo with a valid feed, create a schedule to sync it.

        Do the following:

        1. Create a repository with a valid feed
        2. Schedule sync to run every 30 seconds
        """
        super(CreateSuccessTestCase, cls).setUpClass()
        href, importer_type_id = cls.create_repo()

        # Schedule a sync
        path = urljoin(href, _SCHEDULE_PATH.format(importer_type_id))
        cls.response = api.Client(cls.cfg).post(path, _SCHEDULE)
        cls.response_json = cls.response.json()

    def test_status_code(self):
        """Assert the response has an HTTP 201 status code."""
        self.assertEqual(self.response.status_code, 201)

    def test_total_run_count(self):
        """Verify the ``total_run_count`` attribute in the response."""
        self.assertEqual(self.response_json['total_run_count'], 0)

    def test_enabled(self):
        """Verify the ``enabled`` attribute in the response."""
        self.assertTrue(self.response_json['enabled'])


class CreateFailureTestCase(CreateRepoMixin, utils.BaseAPITestCase):
    """Establish that schedules are not created in `documented scenarios`_.

    .. _documented scenarios:
        https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/sync.html#scheduling-a-sync
    """

    @classmethod
    def setUpClass(cls):
        """Intentionally fail at creating several sync schedules for a repo.

        Each schedule tests a different failure scenario.
        """
        super(CreateFailureTestCase, cls).setUpClass()
        href, importer_type_id = cls.create_repo()

        # We'll need these below.
        scheduling_path = _SCHEDULE_PATH.format(importer_type_id)
        scheduling_path_bad = _SCHEDULE_PATH.format(utils.uuid4())
        bad_repo_path = '{}/{}/'.format(REPOSITORY_PATH, utils.uuid4())

        # Use client to get paths with bodies. Save responses and status_codes.
        client = api.Client(cls.cfg)
        client.response_handler = api.echo_handler
        paths = (
            urljoin(href, scheduling_path),
            urljoin(href, scheduling_path),
            urljoin(href, scheduling_path),
            urljoin(href, scheduling_path),
            urljoin(href, scheduling_path_bad),
            urljoin(bad_repo_path, scheduling_path)
        )
        cls.bodies = (
            {'schedule': None},  # 400
            {'schedule': 'PT30S', 'unknown': 'parameter'},  # 400
            ['Incorrect data type'],  # 400
            {'missing_required_keys': 'schedule'},  # 400
            _SCHEDULE,  # tests incorrect importer in url, 404
            _SCHEDULE,  # tests incorrect repo in url, 404
        )
        cls.responses = tuple((
            client.post(path, body) for path, body in zip(paths, cls.bodies)
        ))
        cls.status_codes = (400, 400, 400, 400, 404, 404)

    def test_status_code(self):
        """Assert that each response has the expected HTTP status code."""
        for body, response, status_code in zip(
                self.bodies,
                self.responses,
                self.status_codes):
            if (body == ['Incorrect data type'] and
                    self.cfg.version < Version('2.8')):
                continue  # https://pulp.plan.io/issues/1745
            with self.subTest(body=body):
                self.assertEqual(response.status_code, status_code)


class ReadUpdateDeleteTestCase(CreateRepoMixin, utils.BaseAPITestCase):
    """Establish that we can `read`_, `update`_ and `delete`_ schedules.

    This test case assumes the assertions in :class:`CreateSuccessTestCase`
    hold true.

    .. _read:
        https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/sync.html#listing-a-single-scheduled-sync
    .. _update:
        https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/sync.html#updating-a-scheduled-sync
    .. _delete:
        https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/sync.html#deleting-a-scheduled-sync
    """

    @classmethod
    def setUpClass(cls):
        """Create three schedules and read, update and delete them."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()
        href, importer_type_id = cls.create_repo()
        cls.schedules = []
        cls.responses = {}
        cls.update_body = {'schedule': 'PT1M'}

        # Create schedules
        client = api.Client(cls.cfg, api.json_handler)
        path = urljoin(href, _SCHEDULE_PATH.format(importer_type_id))
        for _ in range(3):
            cls.schedules.append(client.post(path, _SCHEDULE))

        # Read the first schedule and all schedules, update the second
        # schedule, and delete the third schedule.
        client.response_handler = api.safe_handler
        cls.responses['read_one'] = client.get(cls.schedules[0]['_href'])
        cls.responses['read_many'] = client.get(path)
        cls.responses['update'] = client.put(
            cls.schedules[1]['_href'],
            cls.update_body,
        )
        cls.responses['delete'] = client.delete(cls.schedules[2]['_href'])

    def test_status_code(self):
        """Assert each response has a correct HTTP status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 200)

    def test_read_one(self):
        """Assert the "read_one" response contains the correct attributes."""
        attrs = self.responses['read_one'].json()
        self.assertEqual(set(self.schedules[0]), set(attrs))  # keys
        for key, value in attrs.items():
            if key in _MUTABLE_ATTRS:
                continue
            with self.subTest(key=key):
                self.assertEqual(value, self.schedules[0][key])

    def test_read_many(self):
        """Assert the "read_many" response body contains all schedule hrefs."""
        attrs = self.responses['read_many'].json()
        expected_hrefs = {schedule['_href'] for schedule in self.schedules}
        read_hrefs = {schedule['_href'] for schedule in attrs}
        self.assertEqual(expected_hrefs, read_hrefs)
        # Ensure set deduplication didn't do anything funny.
        self.assertEqual(len(self.schedules), len(attrs))

    def test_update(self):
        """Assert the "update" response body has the correct attributes."""
        expect = self.schedules[1].copy()
        expect.update(self.update_body)
        attrs = self.responses['update'].json()
        self.assertEqual(set(expect), set(attrs))  # keys

        for key, value in expect.items():
            if key in _MUTABLE_ATTRS:
                continue
            with self.subTest(key=key):
                self.assertEqual(value, attrs[key])

    def test_delete(self):
        """Assert the "delete" response body is null."""
        self.assertIsNone(self.responses['delete'].json())


class ScheduledSyncTestCase(CreateRepoMixin, utils.BaseAPITestCase):
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
        href, importer_type_id = cls.create_repo()

        # Schedule a sync to run every 30 seconds. Wait 40 seconds and read it.
        client = api.Client(cls.cfg, api.json_handler)
        schedule_path = urljoin(href, _SCHEDULE_PATH.format(importer_type_id))
        schedule = client.post(schedule_path, _SCHEDULE)
        time.sleep(40)
        cls.response = client.get(schedule['_href'])

    def test_consecutive_failures(self):
        """Assert the sync encountered no consecutive failures."""
        self.assertEqual(self.response['consecutive_failures'], 0)
