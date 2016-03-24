# coding=utf-8
"""Test CRUD for Docker repositories.

This module contains tests for creating Docker repositories. It is intended to
also contain read, update, and delete tests.
"""
from __future__ import unicode_literals

import unittest2

from packaging.version import Version

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
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
    """Show it is possible to update a distributor for a docker repository."""

    @classmethod
    def setUpClass(cls):
        """Create a docker repo with a distributor, and update the distributor.

        Do the following:

        1. Create a docker repository and add a distributor.
        2. Update the distributor. Use the distributor's href in the request.
        3. Update the distributor. Use the repository's href in the request,
           and ensure the distributor is updated by packing certain data in the
           request body.
        """
        super(UpdateTestCase, cls).setUpClass()
        cls.sent_ids = tuple(('test/' + utils.uuid4() for _ in range(2)))
        cls.responses = {}

        # Create a repository and a distributor
        client = api.Client(cls.cfg)
        repo = client.post(REPOSITORY_PATH, _gen_docker_repo_body()).json()
        cls.resources.add(repo['_href'])
        cls.responses['add distributor'] = client.post(
            urljoin(repo['_href'], 'distributors/'),
            _gen_distributor(),
        )
        distributor = cls.responses['add distributor'].json()

        # Update the distributor
        cls.responses['first update'] = client.put(
            distributor['_href'],
            {'distributor_config': {'repo_registry_id': cls.sent_ids[0]}},
        )
        cls.responses['first read'] = client.get(distributor['_href'])

        # Update the distributor again, from repo this time
        cls.responses['second update'] = client.put(
            repo['_href'],
            {'distributor_configs': {distributor['id']: {
                'repo_registry_id': cls.sent_ids[1],
            }}},
        )
        cls.responses['second read'] = client.get(distributor['_href'])

    def test_status_codes(self):
        """Verify each of the server's responses has a correct status code."""
        for step, code in (
                ('add distributor', 201),
                ('first update', 202),
                ('first read', 200),
                ('second update', 202),
                ('second read', 200),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)

    def test_update_accepted(self):
        """Verify the information sent to the server can be read back."""
        read_ids = [
            self.responses[response].json()['config']['repo_registry_id']
            for response in ('first read', 'second read')
        ]
        for i, (sent_id, read_id) in enumerate(zip(self.sent_ids, read_ids)):
            with self.subTest(i=i):
                self.assertEqual(sent_id, read_id)
