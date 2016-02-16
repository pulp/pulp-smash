# coding=utf-8
"""Test CRUD for Docker repositories.

This module contains tests for creating Docker repositories. It is intended to
also contain read, update, and delete tests.
"""
from __future__ import unicode_literals

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
