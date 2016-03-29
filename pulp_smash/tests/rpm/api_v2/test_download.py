# coding=utf-8
"""Tests for the `download_repo`_ task.

This task is designed to download files for content units that have been
added to Pulp by an importer using a deferred download policy. Tests in this
module include ensuring the task downloads units and that its various options
behave as advertised.

.. _download_repo: https://notalinkyetsadly.com/
"""
from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import unittest2
from packaging.version import Version

from pulp_smash import api, utils, cli
from pulp_smash import constants
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo


class SyncDownloadTestCase(utils.BaseAPITestCase):
    """Assert the RPM plugin supports on-demand syncing of yum repositories.

    Beware that this test case will fail if Pulp's Squid server is not
    configured to return an appropriate hostname or IP when performing
    redirection.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository and issue a task to download the repo.

        Do the following:

        1. Reset Pulp.
        2. Create a repository. Sync and publish it using the 'on_demand'
           download policy.
        3. Download the repository
        """
        super(SyncDownloadTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('This test requires Pulp 2.8 or greater.')

        # Ensure Pulp is empty of units otherwise we might just associate pre-
        # existing units.
        utils.reset_pulp(cls.cfg)

        # Make a repo with a feed
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'download_policy': 'on_demand',
            'feed': constants.RPM_FEED_URL,
        }
        distributor = gen_distributor()
        distributor['auto_publish'] = True
        distributor['distributor_config']['relative_url'] = body['id']
        body['distributors'] = [distributor]
        repo = client.post(constants.REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Sync the repo
        sync_path = urljoin(repo['_href'], 'actions/sync/')
        client.post(sync_path, {'override_config': {}})
        cls.pre_download_repo = client.get(
            repo['_href'], params={'details': True})

        # Download the files for a repo
        download_path = urljoin(repo['_href'], 'actions/download/')
        cls.download_task = client.post(
            download_path, json={'verify_all_units': False})
        cls.post_download_repo = client.get(
            repo['_href'], params={'details': True})

        # Corrupt an RPM. The file is there, but the checksum isn't right.
        cli_client = cli.Client(cls.cfg)
        running_as_root = cli_client.run(('id', '-u')).stdout.strip() == '0'
        prefix = '' if running_as_root else 'sudo '
        checksum = cli_client.run(
            (prefix + 'sha256sum ' + constants.RPM_PATH).split())
        cls.pre_corruption_sha = checksum.stdout.strip()
        cli_client.run((prefix + 'rm ' + constants.RPM_PATH).split())
        cli_client.run((prefix + 'touch ' + constants.RPM_PATH).split())
        cli_client.run((prefix + 'chown apache:apache ' +
                        constants.RPM_PATH).split())
        checksum = cli_client.run(
            (prefix + 'sha256sum ' + constants.RPM_PATH).split())
        cls.post_corruption_sha = checksum.stdout.strip()

        # Issue a download task that doesn't checksum all files
        cls.download_task = client.post(
            download_path, json={'verify_all_units': False})
        checksum = cli_client.run(
            (prefix + 'sha256sum ' + constants.RPM_PATH).split())
        cls.unverified_file_sha = checksum.stdout.strip()

        # Issue a download task that does checksum all files
        cls.download_task = client.post(
            download_path, json={'verify_all_units': True})
        checksum = cli_client.run(
            (prefix + 'sha256sum ' + constants.RPM_PATH).split())
        cls.verified_file_sha = checksum.stdout.strip()

    def test_units_before_download(self):
        """Assert no content units were downloaded besides metadata units."""
        pre_download_units = self.pre_download_repo['content_unit_counts']
        metadata_unit_count = sum([
            count for name, count in pre_download_units.items()
            if name not in ('rpm', 'drpm', 'srpm')
        ])
        self.assertEqual(
            self.pre_download_repo['locally_stored_units'],
            metadata_unit_count
        )

    def test_units_after_download(self):
        """Assert all units are downloaded after download_repo finishes."""
        self.assertEqual(self.post_download_repo['locally_stored_units'], 39)

    def test_corruption_occurred(self):
        """Assert the checksum after corrupting an RPM isn't the same.

        This is to ensure we actually corrupted the RPM and validates further
        testing.
        """
        self.assertNotEqual(self.pre_corruption_sha, self.post_corruption_sha)

    def test_unverified_file_unchanged(self):
        """Assert a download without verify_all_units doesn't verify files."""
        self.assertEqual(self.post_corruption_sha, self.unverified_file_sha)

    def test_verified_file_changed(self):
        """Assert a download task with verify_all_units fixes corruption."""
        self.assertEqual(self.pre_corruption_sha, self.verified_file_sha)
