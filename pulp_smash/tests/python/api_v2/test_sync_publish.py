# coding=utf-8
"""Test the sync and publish API endpoints for Python repositories."""
import inspect
import unittest
from os.path import basename
from urllib.parse import urljoin, urlparse

from packaging.version import Version

from pulp_smash import api, config, constants, selectors, utils
from pulp_smash.tests.python.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.python.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class BaseTestCase(unittest.TestCase):
    """A base class for the test cases in this module.

    Test cases derived from this class (should) do the following:

    1. Create and populate a Python repository. The procedure for populating
       the repository varies in each child class.
    2. Create a second Python repository, and sync it from the first.

    In each step, the ``verify_*`` methods are used if appropriate.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.repos = []
        if inspect.getmro(cls)[0] == BaseTestCase:
            raise unittest.SkipTest('Abstract base class.')
        if cls.cfg.version < Version('2.12'):
            raise unittest.SkipTest('This test requires Pulp 2.12 or newer.')

    @classmethod
    def tearDownClass(cls):
        """Delete fixtures and orphans."""
        client = api.Client(cls.cfg)
        for repo in cls.repos:
            client.delete(repo['_href'])
        client.delete(constants.ORPHANS_PATH)

    def test_01_first_repo(self):
        """Create, populate and publish a Python repository.

        Subclasses must override this method.
        """
        raise NotImplementedError

    @selectors.skip_if(len, 'repos', 0)  # require first repo
    def test_02_second_repo(self):
        """Create a second Python repository, and sync it from the first.

        See:

        * `Pulp #140 <https://pulp.plan.io/issues/140>`_
        * `Pulp Smash #493 <https://github.com/PulpQE/pulp-smash/issues/493>`_

        Note that, for `Pulp #140`_ to be fully tested, an additional test case
        should be created wherein one Pulp application syncs from another
        completely independent Pulp application.
        """
        if (self.cfg.version < Version('2.13') or
                selectors.bug_is_untestable(140, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/140')
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'feed': get_repo_path(self.cfg, self.repos[0]),
            'package_names': 'shelf-reader',
        }
        repo = client.post(constants.REPOSITORY_PATH, body)
        self.repos.append(repo)
        call_report = utils.sync_repo(self.cfg, repo)
        with self.subTest(comment='verify the sync succeeded'):
            self.verify_sync(self.cfg, call_report)
        with self.subTest(comment='verify content units are present'):
            self.verify_package_types(self.cfg, repo)

    def verify_sync(self, cfg, call_report):
        """Verify the call to sync a Python repository succeeded.

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

    def verify_package_types(self, cfg, repo):
        """Assert sdist and bdist_wheel shelf-reader packages were synced.

        This test targets `Pulp #1883 <https://pulp.plan.io/issues/1883>`_.
        """
        units = utils.search_units(cfg, repo)
        unit_types = {unit['metadata']['packagetype'] for unit in units}
        self.assertEqual(unit_types, {'sdist', 'bdist_wheel'})


class SyncTestCase(BaseTestCase):
    """Test whether content can be synced into a Python repository."""

    def test_01_first_repo(self):
        """Create, sync content into and publish a Python repository.

        See:

        * `Pulp #135 <https://pulp.plan.io/issues/135>`_
        * `Pulp Smash #494 <https://github.com/PulpQE/pulp-smash/issues/494>`_
        """
        if (self.cfg.version < Version('2.13') or
                selectors.bug_is_untestable(135, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/135')
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'feed': constants.PYTHON_PYPI_FEED_URL,
            'package_names': 'shelf-reader',
        }
        body['distributors'] = [gen_distributor()]
        repo = client.post(constants.REPOSITORY_PATH, body)
        self.repos.append(repo)
        call_report = utils.sync_repo(self.cfg, repo)
        with self.subTest(comment='verify the sync succeeded'):
            self.verify_sync(self.cfg, call_report)
        with self.subTest(comment='verify content units are present'):
            self.verify_package_types(self.cfg, repo)
        repo = get_details(self.cfg, repo)
        utils.publish_repo(self.cfg, repo)


class UploadTestCase(BaseTestCase):
    """Test whether content can be uploaded to a Python repository."""

    def test_01_first_repo(self):
        """Create, upload content into and publish a Python repository.

        See:

        * `Pulp #136 <https://pulp.plan.io/issues/136>`_
        * `Pulp #2334 <https://pulp.plan.io/issues/2334>`_
        * `Pulp Smash #492 <https://github.com/PulpQE/pulp-smash/issues/492>`_
        """
        if (self.cfg.version < Version('2.13') or
                selectors.bug_is_untestable(136, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/136')
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo = client.post(constants.REPOSITORY_PATH, body)
        self.repos.append(repo)

        # A for loop is easier, but it produces hard-to-debug test failures.
        def upload_import_unit(url):
            """Upload and import the unit at ``url`` to ``repo``."""
            unit = utils.http_get(url)
            utils.upload_import_unit(self.cfg, unit, {
                'unit_key': {'filename': basename(urlparse(url).path)},
                'unit_type_id': 'python_package',
            }, repo)

        upload_import_unit(constants.PYTHON_EGG_URL)
        upload_import_unit(constants.PYTHON_WHEEL_URL)
        with self.subTest(comment='verify content units are present'):
            self.verify_package_types(self.cfg, repo)
        repo = get_details(self.cfg, repo)
        utils.publish_repo(self.cfg, repo)


def get_details(cfg, repo):
    """Return detailed information about a Python repository."""
    return api.Client(cfg).get(repo['_href'], params={
        'distributors': True,
        'importers': True,
    }).json()


def get_repo_path(cfg, repo):
    """Return the root path to a published Python repository."""
    path = cfg.base_url
    path = urljoin(path, '/pulp/python/web/')
    path = urljoin(path, repo['id'])
    path += '/'
    return path
