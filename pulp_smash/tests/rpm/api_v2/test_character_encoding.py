# coding=utf-8
"""Tests for Pulp's character encoding handling.

RPM files have metadata embedded in their headers. This metadata should be
encoded as utf-8, and Pulp should gracefully handle cases where invalid byte
sequences are encountered.
"""
import unittest

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM_WITH_NON_ASCII_URL,
    RPM_WITH_NON_UTF_8_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class UploadNonAsciiTestCase(unittest.TestCase):
    """Test whether one can upload an RPM with non-ascii metadata.

    Specifically, do the following:

    1. Create an RPM repository.
    2. Upload and import :data:`pulp_smash.constants.RPM_WITH_NON_ASCII_URL`
       into the repository.
    """

    def test_all(self):
        """Test whether one can upload an RPM with non-ascii metadata."""
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        rpm = utils.http_get(RPM_WITH_NON_ASCII_URL)
        utils.upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)


class UploadNonUtf8TestCase(unittest.TestCase):
    """Test whether one can upload an RPM with non-utf-8 metadata.

    Specifically, do the following:

    1. Create an RPM repository.
    2. Upload and import :data:`pulp_smash.constants.RPM_WITH_NON_UTF_8_URL`
       into the repository.

    This test case targets `Pulp #1903 <https://pulp.plan.io/issues/1903>`_.
    """

    def test_all(self):
        """Test whether one can upload an RPM with non-ascii metadata."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(1903, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1903')
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        rpm = utils.http_get(RPM_WITH_NON_UTF_8_URL)
        utils.upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)
