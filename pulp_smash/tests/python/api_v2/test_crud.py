# coding=utf-8
"""Tests that CRUD Python repositories."""
from __future__ import unicode_literals

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH
from pulp_smash.tests.python.api_v2.utils import gen_repo
from pulp_smash.tests.python.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CRUDTestCase(utils.BaseAPITestCase):
    """Test that one can create, read, update and delete a test case.

    See:

    Create
        http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#create-a-repository
    Read
        http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/retrieval.html#retrieve-a-single-repository
    Update
        http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#update-a-repository
    Delete
        http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#delete-a-repository
    """

    @classmethod
    def setUpClass(cls):
        """Create, update, read and delete a minimal Python repository."""
        super(CRUDTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.bodies = (gen_repo(), {'delta': {'display_name': utils.uuid4()}})
        cls.responses = {}
        cls.responses['create'] = client.post(REPOSITORY_PATH, cls.bodies[0])
        repo_href = cls.responses['create'].json()['_href']
        cls.responses['update'] = client.put(repo_href, cls.bodies[1])
        cls.responses['read'] = client.get(repo_href)
        cls.responses['delete'] = client.delete(repo_href)

    def test_status_codes(self):
        """Assert each response has a correct status code."""
        for response, code in (
                ('create', 201),
                ('update', 200),
                ('read', 200),
                ('delete', 202)):
            with self.subTest((response, code)):
                self.assertEqual(self.responses[response].status_code, code)

    def test_create(self):
        """Assert the repo create response has a correct repo ID."""
        self.assertEqual(
            self.bodies[0]['id'],
            self.responses['create'].json()['id'],
        )

    def test_update(self):
        """Assert the repo update response has the requested changes."""
        self.assertEqual(
            self.bodies[1]['delta']['display_name'],
            self.responses['update'].json()['result']['display_name'],
        )

    def test_read(self):
        """Assert the repo update response has the requested changes."""
        self.assertEqual(
            self.bodies[1]['delta']['display_name'],
            self.responses['read'].json()['display_name'],
        )
