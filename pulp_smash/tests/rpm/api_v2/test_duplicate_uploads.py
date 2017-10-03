# coding=utf-8
"""Tests for how well Pulp can deal with duplicate uploads."""
import hashlib
import os
import unittest
from urllib.parse import urlsplit

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import FILE_URL, REPOSITORY_PATH, RPM_UNSIGNED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class DuplicateUploadsTestCase(unittest.TestCase):
    """Test how well Pulp can deal with duplicate unit uploads."""

    def test_rpm(self):
        """Upload duplicate RPM content.See :meth:`do_test`.

        This test targets the following issues:

        * `Pulp Smash #81 <https://github.com/PulpQE/pulp-smash/issues/81>`_
        * `Pulp #1406 <https://pulp.plan.io/issues/1406>`_
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(1406, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1406')
        body = gen_repo()
        self.do_test(RPM_UNSIGNED_URL, 'rpm', body)

    def test_iso(self):
        """Upload duplicate ISO content. See :meth:`do_test`.

        This test targets the following issues:

        * `Pulp Smash #582 <https://github.com/PulpQE/pulp-smash/issues/582>`_
        * `Pulp #2274 <https://pulp.plan.io/issues/2274>`_
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(2274, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2274')
        body = {
            'id': utils.uuid4(),
            'importer_type_id': 'iso_importer',
            'distributors': [{
                'auto_publish': False,
                'distributor_id': utils.uuid4(),
                'distributor_type_id': 'iso_distributor',
            }],
        }
        iso = utils.http_get(FILE_URL)
        iso_name = os.path.basename(urlsplit(FILE_URL).path)
        unit_key = {
            'checksum': hashlib.sha256(iso).hexdigest(),
            'name': iso_name,
            'size': len(iso),
        }
        self.do_test(FILE_URL, 'iso', body, unit_key)

    def do_test(self, feed, type_id, body, unit_key=None):
        """Test how well Pulp can deal with duplicate unit uploads.

        Do the following:

        1. Create a new feed-less repository.
        2. Upload content and import it into the repository. Assert the
           upload and import was successful.
        3. Upload identical content and import it into the repository.

        The second upload should silently fail for all Pulp releases in the
        2.x series.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        unit = utils.http_get(feed)
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        if unit_key is None:
            unit_key = {}
        for _ in range(0, 2):
            call_report = utils.upload_import_unit(cfg, unit, {
                'unit_type_id': type_id,
                'unit_key': unit_key
            }, repo)
            self.assertIsNone(call_report['result'])
