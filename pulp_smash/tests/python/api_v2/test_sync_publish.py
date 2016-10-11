# coding=utf-8
"""Test the sync and publish API endpoints for Python `repositories`_.
"""

from pulp_smash import api, constants, utils
from pulp_smash.tests.python.api_v2 import utils as python_utils

REPO_CONTENT_SEARCH_URL = '/pulp/api/v2/repositories/{repo}/search/units/'


class SyncPythonRepoTestCase(utils.BaseAPITestCase):
    """If a valid feed is given, the sync completes without reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create a Python repo and sync it."""
        super(SyncPythonRepoTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = python_utils.gen_repo()
        imp_config = {'feed': constants.PYTHON_FEED_URL,
                      'package_names': 'shelf-reader'}
        body['importer_config'] = imp_config
        cls.repo_id = body.get('id')
        cls.repo_href = client.post(constants.REPOSITORY_PATH, body)['_href']
        cls.report = utils.sync_repo(cls.cfg, cls.repo_href)

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details."""
        tasks = tuple(api.poll_spawned_tasks(self.cfg, self.report.json()))
        for i, task in enumerate(tasks):
            step_reports = task['progress_report']['python_importer']
            for step in step_reports:
                with self.subTest(i=i):
                    error_details = step['error_details']
                    self.assertEqual(error_details, [], task)

    def test_multiple_types(self):
        """Verify that we synced the correct number units of each type."""
        repo_search_url = REPO_CONTENT_SEARCH_URL.format(repo=self.repo_id)
        content = api.Client(self.cfg).post(repo_search_url,
                                            {'criteria': {}}).json()

        self.assertEqual(len(content), 2)
        types_in_repo = [content[1]['metadata']['packagetype']]
        types_in_repo.append(content[0]['metadata']['packagetype'])
        self.assertTrue('sdist' in types_in_repo)
        self.assertTrue('bdist_wheel' in types_in_repo)
