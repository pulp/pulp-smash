# coding=utf-8
"""Tests that CRUD Python repositories."""
from pulp_smash import utils
from pulp_smash.tests.python.api_v2.utils import gen_repo
from pulp_smash.tests.python.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CRUDTestCase(utils.BaseAPICrudTestCase):
    """Test that one can create, update, read and delete a test case."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        return gen_repo()

    @staticmethod
    def update_body():
        """Return a dict for creating a repository."""
        return {'delta': {'display_name': utils.uuid4()}}
