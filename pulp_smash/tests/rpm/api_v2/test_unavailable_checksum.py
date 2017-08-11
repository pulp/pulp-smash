# coding=utf-8
"""Tests that publish repositories with unavailable checksum types."""
import unittest

from pulp_smash import api, config, utils
from pulp_smash.constants import (
    DRPM_UNSIGNED_FEED_URL,
    REPOSITORY_PATH,
    RPM_UNSIGNED_FEED_URL,
    SRPM_UNSIGNED_FEED_URL,
)
from pulp_smash.exceptions import TaskReportError
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class UnavailableChecksumTestCase(unittest.TestCase):
    """Publish a lazily-synced repository with unavailable checksum types."""

    def test_rpm(self):
        """Publish a RPM repo. See :meth:`do_test`."""
        self.do_test(RPM_UNSIGNED_FEED_URL, 'rpm')

    def test_srpm(self):
        """Publish a SRPM repo. See :meth:`do_test`."""
        self.do_test(SRPM_UNSIGNED_FEED_URL, 'srpm')

    def test_drpm(self):
        """Publish a DRPM repo. See :meth:`do_test`."""
        self.do_test(DRPM_UNSIGNED_FEED_URL, 'drpm')

    def do_test(self, feed, type_id):
        """Publish a repository with an invalid checksum.

        Do the following:

        1. Create and sync repository of type ``type_id`` and with the given
           feed. Ensure the repository's importer has a deferred/lazy download
           policy.
        2. Determine which checksum type the units in the repository use. (As
           of this writing, Pulp can handle md5, sha1 and sha256 checksum
           types.)
        3. Publish the repository with checksum types different from what the
           units in the repository use. Assert the publish fails.

        This test targets `Pulp Smash #287
        <https://github.com/PulpQE/pulp-smash/issues/287>`_.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        # Create and sync a repository.
        body = gen_repo()
        body['importer_config']['download_policy'] = 'on_demand'
        body['importer_config']['feed'] = feed
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})

        # Figure out which checksum type the units in the repository use.
        units = utils.search_units(cfg, repo, {'type_ids': type_id})
        checksums = {'md5', 'sha1', 'sha256'}

        # Publish this repo with checksums that aren't available.
        checksums -= {units[0]['metadata']['checksumtype']}
        for checksum in checksums:
            client.put(repo['distributors'][0]['_href'], {
                'distributor_config': {'checksum_type': checksum}
            })
            with self.assertRaises(TaskReportError):
                utils.publish_repo(cfg, repo)
