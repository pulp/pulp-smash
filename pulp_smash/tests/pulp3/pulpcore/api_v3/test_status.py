# coding=utf-8
"""Test the status page."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import STATUS_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class StatusTestCase(unittest.TestCase, utils.SmokeTest):
    """Tests related to the status page.

    This test explores the following issues:

    * `Pulp #2804 <https://pulp.plan.io/issues/2804>`_
    * `Pulp #2867 <https://pulp.plan.io/issues/2867>`_
    * `Pulp #3544 <https://pulp.plan.io/issues/3544>`_
    * `Pulp Smash #755 <https://github.com/PulpQE/pulp-smash/issues/755>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.status = {}

    def test_01_access_status(self):
        """Verify whether an un-authenticated user can view status page."""
        self.status.update(self.client.get(STATUS_PATH))

    @selectors.skip_if(bool, 'status', False)
    def test_02_data_content(self):
        """Verify whether few parameters are present on status page."""
        self.assertTrue(self.status['database_connection'])
        self.assertTrue(self.status['messaging_connection'])
        self.assertIsInstance(self.status['online_workers'], list)
        self.assertIsInstance(self.status['missing_workers'], list)
        self.assertIsInstance(self.status['versions'], list)
        self.assertNotEqual(self.status['online_workers'], [])
        self.assertEqual(self.status['missing_workers'], [])
        self.assertNotEqual(self.status['versions'], [])

    def test_03_http_method(self):
        """Verify whether an HTTP exception is raised.

        When using a not allowed HTTP method.
        """
        with self.assertRaises(HTTPError):
            self.client.post(STATUS_PATH)
