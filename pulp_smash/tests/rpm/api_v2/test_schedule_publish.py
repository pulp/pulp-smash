# coding=utf-8
"""Test the API's schedule functionality for repository `publication`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _publication:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html#scheduling-a-publish
"""
import time
from urllib.parse import urljoin

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo, gen_distributor
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CreateSuccessTestCase(utils.BaseAPITestCase):
    """Establish that we can create a schedule to publish the repository."""

    @classmethod
    def setUpClass(cls):
        """Create a schedule to publish the repository.

        Do the following:

        1. Create a repository with a valid feed
        2. Sync it
        3. Schedule publish to run every 30 seconds
        """
        super(CreateSuccessTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)

        # Create a repo with a valid feed and sync it
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Schedule a publish to run every 30 seconds
        distributor = gen_distributor()
        distributor_url = urljoin(repo['_href'], 'distributors/')
        client.post(
            distributor_url,
            distributor
        )
        scheduling_url = urljoin(
            distributor_url,
            '{}/schedules/publish/'.format(distributor['distributor_id']),
        )
        cls.response = client.post(
            scheduling_url,
            {'schedule': 'PT30S'}
        )
        cls.attrs = cls.response.json()

    def test_status_code(self):
        """Assert the response has an HTTP 201 status code."""
        self.assertEqual(self.response.status_code, 201)

    def test_is_enabled(self):
        """Check if sync is enabled."""
        self.assertTrue(self.attrs.get('enabled', False))

    def test_total_run_count(self):
        """Check that ``total_run_count`` is sane."""
        self.assertEqual(self.attrs.get('total_run_count'), 0)


class CreateFailureTestCase(utils.BaseAPITestCase):
    """Establish that schedules are not created in `documented scenarios`_.

    .. _documented scenarios:
        https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html#scheduling-a-publish
    """

    @classmethod
    def setUpClass(cls):
        """Create several schedules.

        Each schedule is created to test a different failure scenario.
        """
        super(CreateFailureTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)

        # Create a repo with a valid feed and sync it
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Add a distibutor
        distributor = gen_distributor()
        client.post(
            urljoin(repo['_href'], 'distributors/'),
            distributor
        )
        client.response_handler = api.echo_handler
        cls.bodies = (
            {'schedule': None},  # 400
            {'unknown': 'parameter', 'schedule': 'PT30S'},  # 400
            ['Incorrect data type'],  # 400
            {'missing_required_keys': 'schedule'},  # 400
            {'schedule': 'PT30S'},  # tests incorrect distributor in url, 404
            {'schedule': 'PT30S'},  # tests incorrect repo in url, 404
        )
        scheduling_url = '/'.join([
            'distributors', distributor['distributor_id'], 'schedules/publish/'
        ])
        bad_distributor_url = '/'.join([
            'distributors', utils.uuid4(), 'schedules/publish/'
        ])
        bad_repo_path = '/'.join([REPOSITORY_PATH, utils.uuid4()])
        cls.paths = (
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], scheduling_url),
            urljoin(repo['_href'], bad_distributor_url),
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
        https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html#listing-a-single-scheduled-publish
    .. _update:
        https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html#updating-a-scheduled-publish
    .. _delete:
        https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html#deleting-a-scheduled-publish
    """

    @classmethod
    def setUpClass(cls):
        """Create three schedules and read, update and delete them."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)

        # Create a repo with a valid feed and sync it
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Create schedules
        distributor = gen_distributor()
        client.post(
            urljoin(repo['_href'], 'distributors/'),
            distributor
        )
        scheduling_url = '/'.join([
            'distributors', distributor['distributor_id'], 'schedules/publish/'
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
        self.assertEqual(len(attrs), len(self.schedules))
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
        attrs = {
            key: attrs[key]
            for key in attrs
            if key not in self.mutable_attrs + list(self.update_body.keys())
        }
        for key in attrs:
            with self.subTest(key=key):
                self.assertEqual(self.schedules[1][key], attrs[key])


class ScheduledPublishTestCase(utils.BaseAPITestCase):
    """Establish that publish runs according to the specified schedule.

    This test case assumes the assertions in :class:`CreateSuccessTestCase`
    and :class:`ReadUpdateDeleteTestCase` hold true.
    """

    @classmethod
    def setUpClass(cls):
        """Create a schedule to publish a repo, verify the ``total_run_count``.

        Do the following:

        1. Create a repository with a valid feed
        2. Sync it
        3. Schedule publish to run every 2 minutes
        4. Wait for 130 seconds and read the schedule to get the number of
           "publish" runs
        """
        super(ScheduledPublishTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)

        # Create a repo with a valid feed and sync it
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Schedule a publish to run every 2 minutes
        distributor = gen_distributor()
        client.post(
            urljoin(repo['_href'], 'distributors/'),
            distributor
        )
        scheduling_url = '/'.join([
            'distributors', distributor['distributor_id'], 'schedules/publish/'
        ])
        schedule_path = urljoin(repo['_href'], scheduling_url)
        schedule = client.post(schedule_path, {'schedule': 'PT2M'})

        # Wait for publish to run
        time.sleep(130)

        # Read the schedule
        cls.response = client.get(schedule['_href'])

    def test_total_run_count(self):
        """Check for the expected total run count."""
        self.assertEqual(self.response['total_run_count'], 2)

    def test_no_failure(self):
        """Make sure any failure ever happened."""
        self.assertEqual(self.response['consecutive_failures'], 0)
