# coding=utf-8
"""Tests that sync and publish RPM repositories.

For information on repository sync and publish operations, see
`Synchronization`_ and `Publication`_.

.. _Publication:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html
.. _Synchronization:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/sync.html
"""
import inspect
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, selectors, utils
from pulp_smash.constants import (
    DRPM_UNSIGNED_FEED_URL,
    REPOSITORY_PATH,
    RPM_FEED_COUNT,
    RPM_FEED_URL,
    SRPM_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


_REPO_PUBLISH_PATH = '/pulp/repos/'  # + relative_url + unit_name.rpm.arch


# This class is left public for documentation purposes.
class SyncRepoBaseTestCase(utils.BaseAPITestCase):
    """A parent class for repository syncronization test cases.

    :meth:`get_feed_url` should be overridden by concrete child classes. This
    method's response is used when setting the repository's importer feed URL.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a valid feed and sync it."""
        if inspect.getmro(cls)[0] == SyncRepoBaseTestCase:
            raise unittest.SkipTest('Abstract base class.')
        super(SyncRepoBaseTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = cls.get_feed_url()
        cls.repo_href = client.post(REPOSITORY_PATH, body)['_href']
        cls.resources.add(cls.repo_href)
        cls.report = utils.sync_repo(cls.cfg, cls.repo_href)

    @staticmethod
    def get_feed_url():
        """Return an RPM repository feed URL. Should be overridden.

        :raises: ``NotImplementedError`` if not overridden by a child class.
        """
        raise NotImplementedError()

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details.

        Other assertions about the final state of each task are handled by the
        client's response handler. (For more information, see the source of
        :func:`pulp_smash.api.safe_handler`.)
        """
        tasks = tuple(api.poll_spawned_tasks(self.cfg, self.report.json()))
        for i, task in enumerate(tasks):
            with self.subTest(i=i):
                error_details = task['progress_report']['yum_importer']['content']['error_details']  # noqa pylint:disable=line-too-long
                self.assertEqual(error_details, [], task)


class SyncRpmRepoTestCase(SyncRepoBaseTestCase):
    """Test one can create and sync an RPM repository with an RPM feed."""

    @staticmethod
    def get_feed_url():
        """Return an RPM repository feed URL."""
        return RPM_FEED_URL

    # This is specific to the RPM repo. Leave in this test case.
    def test_unit_count_on_repo(self):
        """Verify that the sync added the correct number of units to the repo.

        Read the repository and examine its ``content_unit_counts`` attribute.
        Compare these attributes to metadata from the remote repository.
        Expected values are currently hard-coded into this test.
        """
        content_unit_counts = {
            'rpm': RPM_FEED_COUNT,
            'erratum': 4,
            'package_group': 2,
            'package_category': 1,
        }
        if self.cfg.version >= Version('2.9'):  # langpack support added in 2.9
            content_unit_counts['package_langpacks'] = 1
        repo = api.Client(self.cfg).get(self.repo_href).json()
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)

    def test_no_change_in_second_sync(self):
        """Verify that syncing a second time has no changes.

        If the repository have not changed then Pulp must state that anything
        was changed when doing a second sync.
        """
        report = utils.sync_repo(self.cfg, self.repo_href)
        tasks = tuple(api.poll_spawned_tasks(self.cfg, report.json()))
        with self.subTest(comment='spawned tasks'):
            self.assertEqual(len(tasks), 1)
        for count_type in ('added_count', 'removed_count', 'updated_count'):
            with self.subTest(comment=count_type):
                self.assertEqual(tasks[0]['result'][count_type], 0)


class SyncDrpmRepoTestCase(SyncRepoBaseTestCase):
    """Test one can create and sync an RPM repository with an DRPM feed."""

    @staticmethod
    def get_feed_url():
        """Return an DRPM repository feed URL."""
        return DRPM_UNSIGNED_FEED_URL


class SyncSrpmRepoTestCase(SyncRepoBaseTestCase):
    """Test one can create and sync an RPM repository with an SRPM feed."""

    @staticmethod
    def get_feed_url():
        """Return an SRPM repository feed URL."""
        return SRPM_FEED_URL


class SyncInvalidFeedTestCase(utils.BaseAPITestCase):
    """Create an RPM repository with an invalid feed and sync it.

    The sync should complete with errors reported.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with an invalid feed and sync it."""
        super(SyncInvalidFeedTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = utils.uuid4()
        repo = client.post(REPOSITORY_PATH, body)
        client.response_handler = api.echo_handler
        cls.report = client.post(urljoin(repo['_href'], 'actions/sync/'))
        cls.tasks = tuple(api.poll_spawned_tasks(cls.cfg, cls.report.json()))
        cls.resources.add(repo['_href'])

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_error_traceback(self):
        """Assert each task's "error" and "traceback" fields are non-null."""
        if selectors.bug_is_untestable(1455, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1455')
        for i, task in enumerate(self.tasks):
            for key in {'error', 'traceback'}:
                with self.subTest((i, key)):
                    self.assertIsNotNone(task[key])

    def test_task_progress_report(self):
        """Assert each task's progress report contains error details."""
        self.skipTest('https://pulp.plan.io/issues/1376')
        for i, task in enumerate(self.tasks):
            with self.subTest(i=i):
                self.assertNotEqual(
                    task['progress_report']['yum_importer']['content']['error_details'],  # noqa pylint:disable=line-too-long
                    []
                )

    def test_number_tasks(self):
        """Assert that only one task was spawned."""
        self.assertEqual(len(self.tasks), 1)
