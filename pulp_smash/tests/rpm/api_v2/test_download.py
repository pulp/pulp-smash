# coding=utf-8
"""Tests that `download a repository`_.

This module has tests that download files for content units that have been
added to Pulp by an importer using a deferred download policy. Tests in this
module include ensuring the downloads complete and that download options behave
as advertised.

.. _download a repository:
    http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/sync.html#download-a-repository
"""
from __future__ import unicode_literals

import unittest2
from packaging.version import Version

from pulp_smash import api, utils, cli
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_ABS_PATH, RPM_FEED_URL
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
        3. Download the repository.
        4. Corrupt a file in the repository.
        5. Download the repository, without unit verification.
        6. Download the repository, with unit verification.
        """
        super(SyncDownloadTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('This test requires Pulp 2.8 or greater.')

        # Ensure Pulp is empty of units otherwise we might just associate pre-
        # existing units.
        utils.reset_pulp(cls.cfg)

        # Make a repo with a feed
        api_client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {
            'download_policy': 'on_demand',
            'feed': RPM_FEED_URL,
        }
        distributor = gen_distributor()
        distributor['auto_publish'] = True
        distributor['distributor_config']['relative_url'] = body['id']
        body['distributors'] = [distributor]
        repo = api_client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])

        # Sync the repo and download it. Read the repo after both actions.
        params = {'details': True}
        download_path = urljoin(repo['_href'], 'actions/download/')
        api_client.post(
            urljoin(repo['_href'], 'actions/sync/'),
            {'override_config': {}},
        )
        cls.pre_download_repo = api_client.get(repo['_href'], params=params)
        api_client.post(download_path, {'verify_all_units': False})
        cls.post_download_repo = api_client.get(repo['_href'], params=params)

        # Corrupt an RPM. The file is there, but the checksum isn't right.
        cli_client = cli.Client(cls.cfg)
        sudo = '' if utils.is_root(cls.cfg) else 'sudo '
        checksum_cmd = (sudo + 'sha256sum ' + RPM_ABS_PATH).split()
        cls.pre_corruption_sha = cli_client.run(checksum_cmd).stdout.strip()
        cli_client.run((sudo + 'rm ' + RPM_ABS_PATH).split())
        cli_client.run((sudo + 'touch ' + RPM_ABS_PATH).split())
        cli_client.run((sudo + 'chown apache:apache ' + RPM_ABS_PATH).split())
        cls.post_corruption_sha = cli_client.run(checksum_cmd).stdout.strip()

        # Issue a download task that doesn't checksum all files
        api_client.post(download_path, {'verify_all_units': False})
        cls.unverified_file_sha = cli_client.run(checksum_cmd).stdout.strip()

        # Issue a download task that does checksum all files
        api_client.post(download_path, {'verify_all_units': True})
        cls.verified_file_sha = cli_client.run(checksum_cmd).stdout.strip()

    def test_units_before_download(self):
        """Assert no content units were downloaded besides metadata units."""
        locally_stored_units = self.pre_download_repo['locally_stored_units']
        content_unit_counts = self.pre_download_repo['content_unit_counts']
        metadata_unit_count = sum([
            count for name, count in content_unit_counts.items()
            if name not in ('rpm', 'drpm', 'srpm')
        ])
        self.assertEqual(locally_stored_units, metadata_unit_count)

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
