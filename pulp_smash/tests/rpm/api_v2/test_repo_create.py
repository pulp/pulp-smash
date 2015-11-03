# coding=utf-8
"""Test the API endpoints for RPM `repositories`_.

The assumptions explored in this module have the following dependencies::

    # test_create_sync.py
    It is possible to create an RPM repo.
    ├── It is impossible to create a duplicate relative url.
    ├── It is possible to create an RPM repo with feed url. ← TEST THIS
        ├── It is possible to sync repository from feed. ← TEST THIS
    ├── It is possible to create an RPM repo without feed url.
        ├── It is possible to upload single RPM file.
        ├── It is possible to upload directory of RPM files.
        ├── It is possible to upload ISO of RPM files.

    # test_distribute.py
    It is posible to publish an RPM repo with the "???" distributor.
    ...

.. _repositories:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from pulp_smash.constants import REPOSITORY_PATH
from random import randint
from unittest2 import TestCase


_RPM_REPO_URL = 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/zoo/'


def _rand_str():
    """Return a randomized string."""
    return type('')(randint(-999999, 999999))


class CreateFeedTestCase(TestCase):
    """We can create an RPM repository and provide a feed."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a feed."""
        cls.cfg = get_config()
        cls.body = {
            'id': _rand_str(),
            'importer_config': {'feed': _RPM_REPO_URL},
            'importer_type_id': 'yum_importer',
            'notes': {'_repo-type': 'rpm-repo'},
        }
        cls.create_response = requests.post(
            cls.cfg.base_url + REPOSITORY_PATH,
            json=cls.body,
            **cls.cfg.get_requests_kwargs()
        )

        sync_url = cls.create_response.json()['_href'] + 'actions/sync/'
        cls.sync_response = requests.post(
            cls.cfg.base_url + sync_url,
            json={'override_config': {}},
            **cls.cfg.get_requests_kwargs()
        )

    def test_status_code_create(self):
        """Assert that the server returned an HTTP 201."""
        self.assertEqual(self.create_response.status_code, 201)

    def test_status_code_sync(self):
        """Assert that the server returned an HTTP 202."""
        self.assertEqual(self.sync_response.status_code, 202)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repository."""
        requests.delete(
            cls.cfg.base_url + cls.create_response.json()['_href'],
            **cls.cfg.get_requests_kwargs()
        ).raise_for_status()
