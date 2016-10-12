# coding=utf-8
"""Test the sync and publish API endpoints for Python repositories."""
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, constants, selectors, utils
from pulp_smash.tests.python.api_v2.utils import gen_repo
from pulp_smash.tests.python.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class UtilsMixin(object):
    """Methods for use by the test cases in this module.

    Classes inheriting from this mixin must also inherit from
    ``unittest.TestCase``.
    """

    def create_repo(self, cfg, importer_config):
        """Create a Python repository with the given importer config.

        Schedule it for deletion. Return its href.
        """
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = importer_config
        repo_href = client.post(constants.REPOSITORY_PATH, body)['_href']
        self.addCleanup(client.delete, repo_href)
        return repo_href

    def verify_sync(self, cfg, call_report):
        """Verify the call to sync the Python repository succeeded.

        Assert that:

        * The call report has an HTTP 202 status code.
        * None of the tasks spawned by the "sync" request contain errors.
        """
        self.assertEqual(call_report.status_code, 202)
        tasks = tuple(api.poll_spawned_tasks(cfg, call_report.json()))
        for i, task in enumerate(tasks):
            step_reports = task['progress_report']['python_importer']
            for step in step_reports:
                with self.subTest(i=i):
                    error_details = step['error_details']
                    self.assertEqual(error_details, [], task)

    def verify_package_types(self, cfg, repo_href):
        """Assert sdist and bdist_wheel shelf-reader packages were synced.

        This test targets `Pulp #1883 <https://pulp.plan.io/issues/1883>`_.
        """
        if selectors.bug_is_untestable(1883, cfg.version):
            return
        units = api.Client(cfg).post(
            urljoin(repo_href, 'search/units/'),
            {'criteria': {}},
        ).json()
        unit_types = {unit['metadata']['packagetype'] for unit in units}
        self.assertEqual(unit_types, {'sdist', 'bdist_wheel'})


class PulpToPulpSyncTestCase(UtilsMixin, unittest.TestCase):
    """Test whether Pulp can sync from a Pulp Python repository.

    As of pulp_python 2.0, the Python repositories published by Pulp may be
    consumed by other Pulp systems. pulp_python 2.0 is likely to be included in
    Pulp 2.11. This test case will do the following when executed:

    1. Create a Python repository, and set its feed to a Python repository
       created by another Pulp system.
    2. Sync the repository.

    For more information, see:

    * `Pulp #1882 <https://pulp.plan.io/issues/1882>`_
    * `Pulp Smash #416 <https://github.com/PulpQE/pulp-smash/issues/416>`_
    """

    def test_all(self):
        """Test whether Pulp can sync from a Pulp Python repository."""
        cfg = config.get_config()
        if cfg.version < Version('2.11'):
            self.skipTest('https://pulp.plan.io/issues/1882')
        repo_href = self.create_repo(cfg, {
            'feed': constants.PYTHON_PULP_FEED_URL,
            'package_names': 'shelf-reader',
        })
        call_report = utils.sync_repo(cfg, repo_href)
        self.verify_sync(cfg, call_report)
        self.verify_package_types(cfg, repo_href)


class PypiToPulpSyncTestCase(UtilsMixin, unittest.TestCase):
    """Test whether Pulp can sync from a PyPI Python repository.

    As of pulp_python 2.0, the Python repositories published by Pulp may be
    consumed by other Pulp systems. pulp_python 2.0 is likely to be included in
    Pulp 2.11. This test case will do the following when executed:

    1. Create a Python repository, and set its feed to a Python repository
       created by another Pulp system.
    2. Sync the repository.

    For more information, see:

    * `Pulp #1882 <https://pulp.plan.io/issues/1882>`_
    * `Pulp Smash #416 <https://github.com/PulpQE/pulp-smash/issues/416>`_
    """

    def test_all(self):
        """Test whether Pulp can sync from a PyPI Python repository."""
        cfg = config.get_config()
        repo_href = self.create_repo(cfg, {
            'feed': constants.PYTHON_PYPI_FEED_URL,
            'package_names': 'shelf-reader',
        })
        call_report = utils.sync_repo(cfg, repo_href)
        self.verify_sync(cfg, call_report)
        self.verify_package_types(cfg, repo_href)
