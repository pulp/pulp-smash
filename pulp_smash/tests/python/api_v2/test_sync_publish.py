# coding=utf-8
"""Test the sync and publish API endpoints for Python repositories."""
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, constants, selectors, utils
from pulp_smash.tests.python.api_v2.utils import gen_repo
from pulp_smash.tests.python.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class SyncTestCase(utils.BaseAPITestCase):
    """If a valid feed is given, the sync completes without reported errors."""

    @classmethod
    def setUpClass(cls):
        """Create a Python repo and sync it."""
        super(SyncTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'feed': constants.PYTHON_FEED_URL,
            'package_names': 'shelf-reader',
        }
        cls.repo_href = client.post(constants.REPOSITORY_PATH, body)['_href']
        cls.resources.add(cls.repo_href)

    def test_01_sync(self):
        """Sync the repository.

        Assert the call to sync the repository returns an HTTP 202. Assert none
        of the task reports contain error details.
        """
        report = utils.sync_repo(self.cfg, self.repo_href)
        self.assertEqual(report.status_code, 202)
        tasks = tuple(api.poll_spawned_tasks(self.cfg, report.json()))
        for i, task in enumerate(tasks):
            step_reports = task['progress_report']['python_importer']
            for step in step_reports:
                with self.subTest(i=i):
                    error_details = step['error_details']
                    self.assertEqual(error_details, [], task)

    def test_02_package_types(self):
        """Assert sdist and bdist_wheel versions of the package were synced.

        This test targets:

        * `Pulp issue #1882 <https://pulp.plan.io/issues/1882>`_
        * `Pulp issue #2330 <https://pulp.plan.io/issues/2330>`_
        """
        if self.cfg.version < Version('2.11'):
            self.skipTest('https://pulp.plan.io/issues/1882')
        if selectors.bug_is_untestable(2230, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2330')
        units = api.Client(self.cfg).post(
            urljoin(self.repo_href, 'search/units/'),
            {'criteria': {}},
        ).json()
        unit_types = {unit['metadata']['packagetype'] for unit in units}
        self.assertEqual(unit_types, {'sdist', 'bdist_wheel'})
