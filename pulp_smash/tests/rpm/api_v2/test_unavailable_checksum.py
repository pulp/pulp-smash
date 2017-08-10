# coding=utf-8
"""Test to publish repo with lazy content and unavailable checksum type."""
from pulp_smash import api, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM_UNSIGNED_FEED_URL,
    DRPM_UNSIGNED_FEED_URL,
    SRPM_UNSIGNED_FEED_URL,

)
from pulp_smash.exceptions import TaskReportError
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
)
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests if the RPM plugin is not installed."""
    set_up_module()


class UnavailableChecksumTestCase(utils.BaseAPITestCase):
    """Ensure that an exception is raised.

    Assert that an exception is raised when publishing an RPM, DRPM, or SRPM
    repo using an unavailable checksum type.

    """

    @classmethod
    def setUpClass(cls):
        """Provide server config for test execution.

        Do the following:

        1. Reset Pulp, including the Squid cache.
        2. Create a Client.

        """
        super(UnavailableChecksumTestCase, cls).setUpClass()

        # Ensure `locally_stored_units` is 0 before we start.
        utils.reset_squid(cls.cfg)
        utils.reset_pulp(cls.cfg)

        cls.client = api.Client(cls.cfg, api.json_handler)

    def create_sync_repo(self, feed):
        """Create and sync a repository, using on_demand download policy."""
        body = gen_repo()
        body['importer_config']['download_policy'] = 'on_demand'
        body['importer_config']['feed'] = feed
        distributor = gen_distributor()
        body['distributors'] = [distributor]

        # Create repo
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])

        # Sync repo
        utils.sync_repo(self.cfg, repo)

        # Return info related to repo, and distributor
        repo = self.client.get(repo['_href'], params={'details': True})
        return repo, distributor

    def test_all(self):
        """Publishing a repo with an invalid checksum should throw an error.

        1. Create a repository - RPM, SRPM, and DRPM with the "on demand"
        download policy.
        2. Sync the repository.
        3. Get checksum type of an unit.
        4. Update the checksum type.
        5. Attempt to publish the repo with the new checksum.
        6. Assert that an Exception is raised.

        """
        variants = (
            (RPM_UNSIGNED_FEED_URL, 'rpm'),
            (DRPM_UNSIGNED_FEED_URL, 'drpm'),
            (SRPM_UNSIGNED_FEED_URL, 'srpm'),
        )

        for feed, type_id in variants:
            with self.subTest(
                comment='publish unavailable checksum',
                type_id=type_id
            ):

                repo, distributor = self.create_sync_repo(feed)
                units = utils.search_units(
                    self.cfg, repo,
                    {'type_ids': type_id}
                )

                # Get a checksum type different from the received one
                checksum_type = {'md5', 'sha1', 'sha256'}
                checksum_type = checksum_type.difference(
                    {units[0]['metadata']['checksumtype']}
                )

                for checksum in checksum_type:
                    # Update the new checksum type
                    self.client.put(repo['_href'], {
                        'distributor_configs': {
                            distributor['distributor_id']: {
                                'checksum_type': checksum,
                            }
                        }
                    })

                    # Attempt to publish the repo with the new checksum type
                    with self.assertRaises(TaskReportError):
                        # It is expected an Exception to be raised
                        utils.publish_repo(self.cfg, repo)
