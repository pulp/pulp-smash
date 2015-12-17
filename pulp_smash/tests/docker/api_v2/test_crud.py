# coding=utf-8
"""Test CRUD for Docker repositories.

This module contains tests for creating Docker repositories. It is intended to
also contain read, update, and delete tests.

"""
from __future__ import unicode_literals

import unittest2
from packaging.version import Version
from pulp_smash import config, utils


def _gen_docker_repo_body():
    """Generate a Docker repo create body.

    Return a semi-random dict that can be used to create a Docker repository.

    """
    return {
        'id': utils.uuid4(), 'importer_config': {},
        'importer_type_id': 'docker_importer',
        'notes': {'_repo-type': 'docker-repo'},
    }


class _BaseTestCase(unittest2.TestCase):
    """Provide a server config, and tear down created resources."""

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an iterable of resources to delete."""
        cls.cfg = config.get_config()
        cls.attrs_iter = tuple()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require at least Pulp 2.8.')

    @classmethod
    def tearDownClass(cls):
        """Delete created resources."""
        for attrs in cls.attrs_iter:
            utils.delete(cls.cfg, attrs['_href'])


class CreateTestCase(_BaseTestCase):
    """Create two Docker repos, with and without feed URLs respectively."""

    @classmethod
    def setUpClass(cls):
        """Create two Docker repositories, with and without feeds."""
        super(CreateTestCase, cls).setUpClass()
        cls.bodies = tuple((_gen_docker_repo_body() for _ in range(2)))
        cls.bodies[1]['importer_config'] = {
            'feed': 'http://' + utils.uuid4(),  # Pulp checks for URI scheme
        }
        cls.attrs_iter = tuple((
            utils.create_repository(cls.cfg, body) for body in cls.bodies
        ))
        cls.importers_iter = tuple((
            utils.get_importers(cls.cfg, attrs['_href'])
            for attrs in cls.attrs_iter
        ))

    def test_id_notes(self):
        """Validate the ``id`` and ``notes`` attributes for each repo."""
        for key in ('id', 'notes'):
            for body, attrs in zip(self.bodies, self.attrs_iter):
                with self.subTest((key, body, attrs)):
                    self.assertIn(key, attrs)
                    self.assertEqual(body[key], attrs[key])

    def test_number_importers(self):
        """Each repository should have only one importer."""
        for i, importers in enumerate(self.importers_iter):
            with self.subTest(i=i):
                self.assertEqual(len(importers), 1, importers)

    def test_importer_type_id(self):
        """Validate the ``importer_type_id`` attribute of each importer."""
        key = 'importer_type_id'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest((body, importers)):
                self.assertIn(key, importers[0])
                self.assertEqual(body[key], importers[0][key])

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        key = 'config'
        for body, importers in zip(self.bodies, self.importers_iter):
            with self.subTest((body, importers)):
                self.assertIn(key, importers[0])
                self.assertEqual(body['importer_' + key], importers[0][key])
