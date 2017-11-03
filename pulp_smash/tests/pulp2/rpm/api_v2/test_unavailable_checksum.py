# coding=utf-8
"""Tests that publish repositories with unavailable checksum types."""
import unittest

from pulp_smash import api, config, utils
from pulp_smash.constants import (
    DRPM_UNSIGNED_FEED_URL,
    RPM_NAMESPACES,
    RPM_UNSIGNED_FEED_URL,
    SRPM_UNSIGNED_FEED_URL,
)
from pulp_smash.tests.pulp2.constants import REPOSITORY_PATH
from pulp_smash.exceptions import TaskReportError
from pulp_smash.tests.pulp2.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata,
)
from pulp_smash.tests.pulp2.rpm.utils import check_issue_3104
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


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


class UpdatedChecksumTestCase(unittest.TestCase):
    """Ensure that the updated ``checksum_type`` is present on the repo metadata.

    Do the following:

    1. Create, sync and publish a repository with checksum type "sha256".
    2. After that several XML files - part of repodata will be inspected.

       ``primary.xml``
           Assert that the given checksum type is the only one present.
       ``filelists.xml`` and ``other.xml``
           Assert that the length of ``pkgid`` is according to the given
           checksum type.
       ``prestodelta.xml``
           Assert that the given checksum type is the only one present.

       For ``sha256`` the length of ``pkgid`` should be 64 hex digits, and for
       ``sha1`` the length should be 40 hex digits. For DRPM repositories the
       ``prestodelta.xml`` will be inspected as well.

    3. Update the checksum type to "sha1", and use option ``force_full`` set as
       True. ``force_full`` will force a complete re-publish to happen.
       Re-publish the repository.
    4. All aforementioned assertions performed on the step 2 will be executed
       again to assure that new checksum type was updating properly.

    This test targets `Pulp Smash #286
    <https://github.com/PulpQE/pulp-smash/issues/286>`_.
    """

    def test_rpm(self):
        """Verify update checksum in a RPM repo. See :meth:`do_test`."""
        self.do_test(RPM_UNSIGNED_FEED_URL)

    def test_srpm(self):
        """Verify updated checksum in a SRPM repo. See :meth:`do_test`."""
        self.do_test(SRPM_UNSIGNED_FEED_URL)

    def test_drpm(self):
        """Verify updated checksum in a DRPM repo. See :meth:`do_test`."""
        self.do_test(DRPM_UNSIGNED_FEED_URL)

    def do_test(self, feed):
        """Verify ``checksum_type`` is updated on the repo metadata."""
        cfg = config.get_config()
        if check_issue_3104(cfg):
            self.skipTest('https://pulp.plan.io/issues/3104')
        client = api.Client(cfg, api.json_handler)

        # Create and sync a repository.
        body = gen_repo()
        body['importer_config']['feed'] = feed
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        distributor = repo['distributors'][0]

        # Update checksum type to be "sha256" and publish the repository.
        client.put(distributor['_href'], {
            'distributor_config': {'checksum_type': 'sha256'}
        })
        utils.publish_repo(cfg, repo)
        with self.subTest(comment='primary.xml'):
            self.verify_primary_xml(cfg, distributor, 'sha256')
        with self.subTest(comment='filelists.xml'):
            self.verify_filelists_xml(cfg, distributor, 'sha256')
        with self.subTest(comment='other.xml'):
            self.verify_other_xml(cfg, distributor, 'sha256')
        if feed == DRPM_UNSIGNED_FEED_URL:
            with self.subTest(comment='prestodelta.xml'):
                self.verify_presto_delta_xml(cfg, distributor, 'sha256')

        # Update the checksum type to "sha1", and re-publish the repository.
        client.put(distributor['_href'], {
            'distributor_config': {'checksum_type': 'sha1', 'force_full': True}
        })
        utils.publish_repo(cfg, repo)
        with self.subTest(comment='primary.xml'):
            self.verify_primary_xml(cfg, distributor, 'sha1')
        with self.subTest(comment='filelists.xml'):
            self.verify_filelists_xml(cfg, distributor, 'sha1')
        with self.subTest(comment='other.xml'):
            self.verify_other_xml(cfg, distributor, 'sha1')
        if feed == DRPM_UNSIGNED_FEED_URL:
            with self.subTest(comment='prestodelta.xml'):
                self.verify_presto_delta_xml(cfg, distributor, 'sha1')

    def verify_primary_xml(self, cfg, distributor, checksum_type):
        """Verify a published repo's primary.xml uses the given checksum."""
        primary_xml = get_repodata(cfg, distributor, 'primary')
        xpath = '{{{}}}package'.format(RPM_NAMESPACES['metadata/common'])
        packages = primary_xml.findall(xpath)
        xpath = '{{{}}}checksum'.format(RPM_NAMESPACES['metadata/common'])
        checksum_types = {
            package.find(xpath).get('type') for package in packages
        }
        self.assertEqual(checksum_types, {checksum_type})

    def verify_filelists_xml(self, cfg, distributor, checksum_type):
        """Verify a published repo's filelists.xml uses the given checksum."""
        filelist_xml = get_repodata(cfg, distributor, 'filelists')
        xpath = '{{{}}}package'.format(RPM_NAMESPACES['metadata/filelists'])
        packages = filelist_xml.findall(xpath)
        pkgids_len = {len(package.get('pkgid')) for package in packages}
        self.verify_pkgid_len(pkgids_len, checksum_type)

    def verify_other_xml(self, cfg, distributor, checksum_type):
        """Verify a published repo's other.xml uses the given checksum."""
        other_xml = get_repodata(cfg, distributor, 'other')
        xpath = '{{{}}}package'.format(RPM_NAMESPACES['metadata/other'])
        packages = other_xml.findall(xpath)
        pkgids_len = {len(package.get('pkgid')) for package in packages}
        self.verify_pkgid_len(pkgids_len, checksum_type)

    def verify_pkgid_len(self, pkgid_len, checksum_type):
        """Perform assertion based on the given checksum type.

        Based on the checksum type provided different assertions will
        be performed over the length of ``pkgid``.
        """
        if checksum_type == 'sha256':
            # 256 bits / (4 bits / 1 hex digit) = 64 hex digits.
            self.assertEqual(pkgid_len, {64})
        if checksum_type == 'sha1':
            # 160 bits / (4 bits / 1 hex digit) = 40 hex digits.
            self.assertEqual(pkgid_len, {40})

    def verify_presto_delta_xml(self, cfg, distributor, checksum_type):
        """Verify a published repo's prestodelta.xml uses given checksum."""
        presto_delta_xml = get_repodata(cfg, distributor, 'prestodelta')
        checksum_types = {
            node.attrib.get('type')
            for node in presto_delta_xml.iter('checksum')
        }
        self.assertEqual(checksum_types, {checksum_type})
