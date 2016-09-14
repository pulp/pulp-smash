# coding=utf-8
"""Tests that CRUD RPM repositories.

For information on repository CRUD operations, see `Creation, Deletion and
Configuration
<http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html>`_.
"""
import unittest

from packaging import version

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH, REPOSITORY_GROUP_PATH
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    gen_repo_group
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CrudTestCase(utils.BaseAPICrudTestCase):
    """CRUD a minimal RPM repository."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        return gen_repo()

    @staticmethod
    def update_body():
        """Return a dict for updating a repository."""
        return {'delta': {'display_name': utils.uuid4()}}


class CrudWithFeedTestCase(CrudTestCase):
    """CRUD an RPM repository with a feed URL."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        body = CrudTestCase.create_body()
        body['importer_config'] = {'feed': utils.uuid4()}
        return body


class RepositoryGroupCrudTestCase(utils.BaseAPITestCase):
    """CRUD a minimal RPM repositories' groups.

    For information on repositories' groups CRUD operations, see `Creation,
    Delete, and Update
    <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/groups/cud.html>`
    """

    @classmethod
    def setUpClass(cls):
        """Create, update, read and delete a repository group."""
        super(RepositoryGroupCrudTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.bodies = {
            'create': gen_repo_group(),
            'update': {'display_name': utils.uuid4()},
        }
        cls.responses = {}
        cls.responses['create'] = client.post(
            REPOSITORY_GROUP_PATH,
            cls.bodies['create'],
        )
        repo_href = cls.responses['create'].json()['_href']
        cls.responses['update'] = client.put(repo_href, cls.bodies['update'])
        cls.responses['read'] = client.get(repo_href, params={'details': True})
        cls.responses['delete'] = client.delete(repo_href)

    def test_status_codes(self):
        """Assert each response has a correct status code."""
        for response, code in (
                ('create', 201),
                ('update', 200),
                ('read', 200),
                ('delete', 200)):
            with self.subTest((response, code)):
                self.assertEqual(self.responses[response].status_code, code)

    def test_create(self):
        """Assert the created repository group has all requested attributes.

        Walk through each of the attributes present on the create body and
        verify the attribute is present in the repository group.
        """
        received = self.responses['create'].json()
        for key, value in self.bodies['create'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_update(self):
        """Assert the repo group update response has the requested changes."""
        received = self.responses['update'].json()
        for key, value in self.bodies['update'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_read(self):
        """Assert the repo group update response has the requested changes."""
        received = self.responses['read'].json()
        for key, value in self.bodies['update'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)


class RPMDistributorTestCase(utils.BaseAPITestCase):
    """RPM distributor tests."""

    def test_update_checksum_type(self):
        """Check if RPM distributor can receive null checksum_type.

        See: https://pulp.plan.io/issues/2134.
        """
        if self.cfg.version < version.Version('2.9'):
            raise unittest.SkipTest('This test requires Pulp 2.9 or above.')
        client = api.Client(self.cfg, api.json_handler)
        distributor = gen_distributor()
        body = gen_repo()
        body['distributors'] = [distributor]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        for checksum_type in (None, 'sha256', None):
            client.put(repo['_href'], {
                'distributor_configs': {
                    distributor['distributor_id']: {
                        'checksum_type': checksum_type,
                    }
                }
            })
            repo = client.get(repo['_href'], params={'details': True})
            config = repo['distributors'][0]['config']
            self.assertEqual(config.get('checksum_type'), checksum_type)
