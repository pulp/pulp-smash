# coding=utf-8
"""Tests that perform actions over content unit."""
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import FILE_URL
from pulp_smash.tests.pulp3.constants import ARTIFACTS_PATH, FILE_CONTENT_PATH
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.pulp3.utils import clean_artifacts, get_auth


class ContentUnitTestCase(unittest.TestCase, utils.SmokeTest):
    """CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp Smash #870 <https://github.com/PulpQE/pulp-smash/issues/870>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        cls.cfg = config.get_config()
        clean_artifacts(cls.cfg)
        cls.content_unit = {}
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        files = {'file': utils.http_get(FILE_URL)}
        cls.artifact = cls.client.post(ARTIFACTS_PATH, files=files)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        cls.client.delete(cls.artifact['_href'])

    def test_01_create_content_unit(self):
        """Create content unit."""
        attrs = _gen_content_unit_attrs(self.artifact)
        self.content_unit.update(self.client.post(FILE_CONTENT_PATH, attrs))
        for key, val in attrs.items():
            with self.subTest(key=key):
                self.assertEqual(self.content_unit[key], val)

    @selectors.skip_if(bool, 'content_unit', False)
    def test_02_read_content_unit(self):
        """Read a content unit by its href."""
        content_unit = self.client.get(self.content_unit['_href'])
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(content_unit[key], val)

    @selectors.skip_if(bool, 'content_unit', False)
    def test_03_partially_update(self):
        """Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = _gen_content_unit_attrs(self.artifact)
        with self.assertRaises(HTTPError):
            self.client.patch(self.content_unit['_href'], attrs)

    @selectors.skip_if(bool, 'content_unit', False)
    def test_03_fully_update(self):
        """Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = _gen_content_unit_attrs(self.artifact)
        with self.assertRaises(HTTPError):
            self.client.put(self.content_unit['_href'], attrs)

    @selectors.skip_if(bool, 'content_unit', False)
    def test_04_delete_content_unit(self):
        """Delete a content unit."""
        self.client.delete(self.content_unit['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.content_unit['_href'])


def _gen_content_unit_attrs(artifact):
    """Generate a dict with content unit attributes.

    :param: artifact: A dict of info about the artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    return {'artifact': artifact['_href'], 'relative_path': utils.uuid4()}
