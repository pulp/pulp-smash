# coding=utf-8
"""Test the CRUD API endpoints `OSTree`_ `repositories`_.

TODO (asmacdo) review what is where in the docs here


This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an OSTree repo with feed (CreateTestCase).
    It is possible to create a repository without a feed (CreateTestCase).

.. _OSTree:
    http://pulp-ostree.readthedocs.org/en/latest/
.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from __future__ import unicode_literals

from pulp_smash import api, utils
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
