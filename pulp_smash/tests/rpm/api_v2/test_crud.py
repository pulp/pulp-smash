# coding=utf-8
"""Tests that CRUD RPM repositories.

For information on repository CRUD operations, see `Creation, Deletion and
Configuration
<http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/cud.html>`_.
"""
from __future__ import unicode_literals

from pulp_smash import utils
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
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
