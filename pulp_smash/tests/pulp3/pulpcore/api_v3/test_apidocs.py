# coding=utf-8
"""Test the apidocs page."""
import unittest

from pulp_smash import api, config, utils
from pulp_smash.tests.pulp3.constants import APIDOCS_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class ApidocsTestCase(unittest.TestCase, utils.SmokeTest):
    """Tests related to the apidocs page."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.status = {}

    def test_01_access_apidocs(self):
        """Verify whether we can reach the api docs page."""
        self.client.get(APIDOCS_PATH)
