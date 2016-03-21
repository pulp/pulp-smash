# coding=utf-8
"""Test the CRUD API endpoints `OSTree`_ `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an OSTree repo with feed (CreateTestCase).
    It is possible to create a repository without a feed (CreateTestCase).
      It is possible to create distributors for a repo
        It is not possible to create distributors to have conflicting paths
        It is not possible to update distrubutors to have conflicting paths

.. _OSTree:
    http://pulp-ostree.readthedocs.org/en/latest/
.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from __future__ import unicode_literals
import copy

from pulp_smash import api, selectors, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH
from pulp_smash.tests.ostree.utils import gen_repo, skip_if_no_plugin


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests if the OSTree plugin is not installed."""
    skip_if_no_plugin()


class CreateTestCase(utils.BaseAPITestCase):
    """Create two OSTree repositories, with and without a feed."""

    @classmethod
    def setUpClass(cls):
        """Create two repositories."""
        super(CreateTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        cls.bodies = tuple((gen_repo() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {'feed': utils.uuid4()}
        cls.repos = [client.post(REPOSITORY_PATH, body) for body in cls.bodies]
        cls.importers_iter = [
            client.get(urljoin(repo['_href'], 'importers/'))
            for repo in cls.repos
        ]
        for repo in cls.repos:
            cls.resources.add(repo['_href'])  # mark for deletion

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repository."""
        for body, repo in zip(self.bodies, self.repos):  # for input, output:
            for key in {'id', 'notes'}:
                with self.subTest(body=body):
                    self.assertIn(key, repo)
                    self.assertEqual(repo[key], body[key])

    def test_number_importers(self):
        """Assert each repository has one importer."""
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertEqual(len(importers), 1, importers)

    def test_importer_type_id(self):
        """Validate the ``importer_type_id`` attribute of each importer."""
        key = 'importer_type_id'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(importers[0][key], body[key])

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        key = 'config'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(importers[0][key], body['importer_' + key])


class CreateDistributors(utils.BaseAPITestCase):
    """Test the creation of ostree distributors."""

    @classmethod
    def setUpClass(cls):
        """Create distributors that have conflicting relative_paths."""
        if selectors.bug_is_untestable(1106):
            cls.skipTest(cls, 'https://pulp.plan.io/issues/1106')
        super(CreateDistributors, cls).setUpClass()
        client = api.Client(cls.cfg, api.echo_handler)
        cls.bodies = tuple((gen_repo() for _ in range(2)))
        cls.repos = [client.post(REPOSITORY_PATH, body) for body in cls.bodies]
        empty_dist = {'distributor_type_id': 'ostree_web_distributor',
                      'config': {}}

        for repo in cls.repos:
            cls.resources.add(repo.json()['_href'])  # mark for deletion

        # Create distributors to test whether their paths collide.
        dist_1 = copy.deepcopy(empty_dist)
        dist_2 = copy.deepcopy(empty_dist)
        dist_3 = copy.deepcopy(empty_dist)
        dist_4 = copy.deepcopy(empty_dist)
        dist_5 = copy.deepcopy(empty_dist)
        dist_1['distributor_config'] = {'relative_path': 'test/path'}
        dist_2['distributor_config'] = {'relative_path': 'test/path'}
        dist_3['distributor_config'] = {'relative_path': 'different/test/path'}
        dist_4['distributor_config'] = {'relative_path': '/test/path'}
        dist_5['distributor_config'] = {'relative_path': 'test/path/extended'}
        repo1_url = urljoin(cls.repos[0].json()['_href'], 'distributors/')
        repo2_url = urljoin(cls.repos[1].json()['_href'], 'distributors/')
        cls.create_resp = client.post(repo1_url, dist_1)
        cls.direct_conflict = client.post(repo2_url, dist_2)
        cls.second_valid = client.post(repo2_url, dist_3)
        cls.leading_slash = client.post(repo2_url, dist_4)
        cls.sub_url = client.post(repo2_url, dist_5)

    def test_sanity(self):
        """Ensure the first distributor was successful."""
        self.assertEqual(self.create_resp.status_code, 201)

    def test_conflict(self):
        """Ensure that a 400 is raised when there is a direct conflict."""
        self.assertEqual(self.direct_conflict.status_code, 400)

    def test_second_valid(self):
        """Create a second distributor with a nonconflicting relative_path."""
        self.assertEqual(self.second_valid.status_code, 201)

    def test_leading_slash(self):
        """Ensure that a leading slash does not affect confict find."""
        self.assertEqual(self.leading_slash.status_code, 400)

    def test_sub_url_conflict_detection(self):
        """Ensure that conflicts with sub urls are detected."""
        self.assertEqual(self.sub_url.status_code, 400)


class UpdateDistributors(utils.BaseAPITestCase):
    """Test the update of ostree distributors."""

    @classmethod
    def setUpClass(cls):
        """Create distributors and update with conflicting relative_paths."""
        super(UpdateDistributors, cls).setUpClass()
        if selectors.bug_is_untestable(1106):
            cls.skipTest(cls, 'https://pulp.plan.io/issues/1106')
        client = api.Client(cls.cfg, api.echo_handler)
        cls.bodies = tuple((gen_repo() for _ in range(3)))
        cls.repos = [client.post(REPOSITORY_PATH, body) for body in cls.bodies]
        empty_dist = {'distributor_type_id': 'ostree_web_distributor',
                      'config': {}}

        for repo in cls.repos:
            cls.resources.add(repo.json()['_href'])  # mark for deletion

        # Create distributors to test whether their paths collide.
        dist_1 = copy.deepcopy(empty_dist)
        dist_2 = copy.deepcopy(empty_dist)
        dist_3 = copy.deepcopy(empty_dist)
        dist_1['distributor_config'] = {'relative_path': 'conflict/with/this'}
        dist_2['distributor_config'] = {'relative_path': 'original/path'}
        dist_3['distributor_config'] = {
            'relative_path': 'another/original/path'
        }
        repo1_url = urljoin(cls.repos[0].json()['_href'], 'distributors/')
        repo2_url = urljoin(cls.repos[1].json()['_href'], 'distributors/')
        cls.create_resp_1 = client.post(repo1_url, dist_1)
        cls.create_resp_2 = client.post(repo2_url, dist_2)
        cls.create_resp_3 = client.post(repo2_url, dist_3)
        dist_2_url = cls.create_resp_2.json()['_href']
        dist_2['distributor_config']['relative_path'] = 'test/updated'
        dist_3_url = cls.create_resp_3.json()['_href']
        dist_3['distributor_config']['relative_path'] = 'conflict/with/this'
        cls.update_resp_1 = client.put(dist_2_url, dist_2)
        cls.update_resp_2 = client.put(dist_3_url, dist_3)
        cls.get_update_succeed = client.get(dist_2_url)
        cls.get_update_conflict = client.get(dist_3_url)

    def test_creation(self):
        """Ensure that distributors were created."""
        self.assertEqual(self.create_resp_1.status_code, 201)
        self.assertEqual(self.create_resp_2.status_code, 201)
        self.assertEqual(self.create_resp_3.status_code, 201)

    def test_update_creates_tasks(self):
        """Ensure that updates return 202, even if they are invalid."""
        self.assertEqual(self.update_resp_1.status_code, 202)
        self.assertEqual(self.update_resp_2.status_code, 202)

    def test_get_update_succeed(self):
        """Ensure that a valid config update actually updated the config."""
        update_path = self.get_update_succeed.json()['config']['relative_path']
        self.assertEqual(self.get_update_succeed.status_code, 200)
        self.assertEqual(update_path, 'test/updated')

    def test_get_update_conflict(self):
        """Ensure that a conflicting config update does not update config."""
        rel_path = self.get_update_conflict.json()['config']['relative_path']
        self.assertEqual(self.get_update_succeed.status_code, 200)
        self.assertEqual(rel_path, 'another/original/path')
