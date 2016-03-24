# coding=utf-8
"""Test CRUD for Docker repositories.

This module contains tests for creating Docker repositories. It is intended to
also contain read, update, and delete tests.
"""
from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import unittest2

from packaging.version import Version

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH


def _gen_docker_repo_body():
    """Generate a Docker repo create body.

    Return a semi-random dict that can be used to create a Docker repository.
    """
    return {
        'id': utils.uuid4(), 'importer_config': {},
        'importer_type_id': 'docker_importer',
        'notes': {'_repo-type': 'docker-repo'},
    }


def _gen_distributor():
    """Return a semi-random dict for use in creating a docker distributor."""
    return {
        'auto_publish': False,
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'docker_distributor_web',
        'distributor_config': {
            'http': True,
            'https': True,
        },
    }


class _BaseTestCase(utils.BaseAPITestCase):
    """Provide logic common to docker test cases."""

    @classmethod
    def setUpClass(cls):
        """Skip tests if the targeted Pulp system is older than version 2.8."""
        super(_BaseTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require at least Pulp 2.8.')


class CreateTestCase(_BaseTestCase):
    """Create two Docker repos, with and without feed URLs respectively."""

    @classmethod
    def setUpClass(cls):
        """Create two Docker repositories, with and without feeds."""
        super(CreateTestCase, cls).setUpClass()
        cls.bodies = tuple((_gen_docker_repo_body() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {'feed': 'http://' + utils.uuid4()}

        client = api.Client(cls.cfg, api.json_handler)
        cls.repos = []
        cls.importers_iter = []
        for body in cls.bodies:
            repo = client.post(REPOSITORY_PATH, body)
            cls.repos.append(repo)
            cls.resources.add(repo['_href'])
            cls.importers_iter.append(client.get(repo['_href'] + 'importers/'))

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repo."""
        for body, repo in zip(self.bodies, self.repos):  # for input, output:
            for key in {'id', 'notes'}:
                with self.subTest(body=body):
                    self.assertIn(key, repo)
                    self.assertEqual(body[key], repo[key])

    def test_number_importers(self):
        """Each repository should have only one importer."""
        for i, importers in enumerate(self.importers_iter):
            with self.subTest(i=i):
                self.assertEqual(len(importers), 1, importers)

    def test_importer_type_id(self):
        """Validate the ``importer_type_id`` attribute of each importer."""
        key = 'importer_type_id'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(body[key], importers[0][key])

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        key = 'config'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest(body=body):
                self.assertIn(key, importers[0])
                self.assertEqual(body['importer_' + key], importers[0][key])


class UpdateTestCase(_BaseTestCase):
    """Create Docker repo, add and update distributor."""

    @classmethod
    def setUpClass(cls):
        """Create Docker repository, add and update distributor."""
        super(UpdateTestCase, cls).setUpClass()
        cls.responses = {}
        cls.body = _gen_docker_repo_body()
        client = api.Client(cls.cfg, api.json_handler)
        cls.repo = client.post(REPOSITORY_PATH, cls.body)
        cls.resources.add(cls.repo['_href'])
        client.response_handler = api.safe_handler

        # Add distributor
        cls.responses['distribute'] = client.post(
            urljoin(cls.repo['_href'], 'distributors/'),
            _gen_distributor(),
        )
        # Get distributor
        cls.dist = client.get(cls.repo['_href'] + 'distributors/').json()

        # Update distributor
        cls.responses['update_distrib'] = client.put(
            cls.dist[0]['_href'],
            {'distributor_config': {'repo_registry_id': 'test/vtest'}}
        )

        # Update distributor from repo
        body = {'distributor_configs': {
            cls.dist[0]['id']: {'repo_registry_id': 'test/vtest'}}}
        cls.responses['update_distrib_2'] = client.put(
            cls.repo['_href'], body
        )

    def test_update_distributor(self):
        """Verify that creation and update of distirbutor works as expected."""
        self.assertEqual(self.responses['distribute'].status_code, 201)
        self.assertEqual(self.responses['update_distrib'].status_code, 202)
        self.assertEqual(self.responses['update_distrib_2'].status_code, 202)
