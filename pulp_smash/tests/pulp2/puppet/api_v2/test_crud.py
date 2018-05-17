# coding=utf-8
"""Tests that CRUD Puppet repositories."""
from pulp_smash import utils
from pulp_smash.pulp2.utils import BaseAPICrudTestCase
from pulp_smash.tests.pulp2.puppet.api_v2.utils import gen_repo
from pulp_smash.tests.pulp2.puppet.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class CRUDTestCase(BaseAPICrudTestCase):
    """Test that one can create, update, read and delete a test case."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        return gen_repo()

    @staticmethod
    def update_body():
        """Return a dict for creating a repository."""
        return {'delta': {'display_name': utils.uuid4()}}
