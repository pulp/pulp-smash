# coding=utf-8
"""Tests that upload content units into repositories."""
import os
import unittest
import urllib

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import (
    DRPM,
    DRPM_UNSIGNED_URL,
    RPM_WITH_VENDOR,
    RPM_WITH_VENDOR_URL,
    RPM_WITH_VENDOR_DATA,
)
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login`` on the target Pulp system."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


class _BaseCLIDownloadTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cfg = config.get_config()
        cls.client = cli.Client(cls.cfg)

    def temp_download(self, file_url, filename='tmp.rpm'):
        """Download a file from the given url to a temp directory.

        Args:
            file_url: String. The URL of the file to download. Required
            filename: String. Assigns a name to the file downloaded. Optional.

        Returns:
            String. Full path to file downloaded.

        After the test case runs, the temp directory and file is destroyed.

        """
        temp_dir = self.client.run('mktemp --directory'.split()).stdout.strip()
        self.addCleanup(self.client.run, 'rm -rf {}'.format(temp_dir).split())
        file_path = os.path.join(temp_dir, os.path.split(filename)[-1])
        try:
            self.client.run(
                'curl -o {} {}'.format(file_path, file_url).split()
            )
        except urllib.error.HTTPError:
            raise self.skipTest('Skipping test, could not download resource')

        return file_path

    def create_repo(self, plugin, repo_id):
        """Create a repo with given plugin.

        Args:
            plugin: String. Name of plugin. Required
            repo_id: String. Name of repo to be created. Required

        Returns:
            Completed process

        After the test case runs, the repo is destroyed.

        """
        result = self.client.run(
            'pulp-admin {} repo create --repo-id {}'
            .format(plugin, repo_id).split()
        )
        self.addCleanup(
            self.client.run,
            'pulp-admin {} repo delete --repo-id {}'
            .format(plugin, repo_id).split()
        )
        return result

    def upload_to_repo(self, **kwargs):
        """Upload a file to a repo.

        Args:
            plugin: String. Name of plugin. Required
            filetype: String. Name of filetype. Required
            filename: String. Full path of file. Required
            args: String. Additional arguments to uploads command. Optional

        Returns:
            Completed process.

        """
        if 'args' not in kwargs.keys():
            kwargs['args'] = ''
        return self.client.run(
            'pulp-admin {} repo uploads {} --repo-id {} --file {} {}'
            .format(
                kwargs['plugin'],
                kwargs['filetype'],
                kwargs['repo_id'],
                kwargs['filename'],
                kwargs['args']
            ).split()
        )

    def check_field(self, **kwargs):
        """Check that the expected output is in the result of search query.

        Args:
            plugin: String. Name of plugin. Required
            filetype: String. Name of filetype. Required
            repo_id: String. Name of repo to be searched. Required
            expected: String. Expected content of search querey. Required
            search_field: String. Field to be searched for. Required
                    Examples: filename, vendor, group, summary
        Returns:
            Completed process.
        """
        proc = self.client.run(
            'pulp-admin {} repo content {} --repo-id {} --fields {}'
            .format(
                kwargs['plugin'],
                kwargs['filetype'],
                kwargs['repo_id'],
                kwargs['search_field']
            ).split()
        )
        self.assertIn(kwargs['expected'], proc.stdout.split())
        return proc


class UploadDrpmTestCase(_BaseCLIDownloadTestCase):
    """Test whether one can upload a DRPM into a repository.

    This test case targets `Pulp Smash #336
    <https://github.com/PulpQE/pulp-smash/issues/336>`_ and
    `Pulp Smash #585 <https://github.com/PulpQE/pulp-smash/issues/585>`_
    """

    def test_upload(self):
        """Create a repository and upload DRPMs into it.

        Specifically, do the following:

        1. Create a yum repository.
        2. Download a DRPM file.
        3. Upload the DRPM into it. Use ``pulp-admin`` to verify its presence
           in the repository.
        4. Upload the same DRPM into the same repository, and use the
           ``--skip-existing`` flag during the upload. Verify that Pulp skips
           the upload.
        """
        if selectors.bug_is_untestable(1806, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1806')

        # Create a repository
        repo_id = utils.uuid4()
        self.create_repo('rpm', repo_id)
        drpm_file_path = self.temp_download(DRPM_UNSIGNED_URL, DRPM)

        # Upload the DRPM into the repository. Don't use subTest, as if this
        # test fails, the following one is invalid anyway.
        self.upload_to_repo(
            plugin='rpm',
            filetype='drpm',
            repo_id=repo_id,
            filename=drpm_file_path,
        )
        self.check_field(
            plugin='rpm',
            filetype='drpm',
            repo_id=repo_id,
            expected=DRPM,
            search_field='filename'
        )

        # Upload the DRPM into the repository. Pass --skip-existing.
        proc = self.upload_to_repo(
            plugin='rpm',
            filetype='drpm',
            repo_id=repo_id,
            filename=drpm_file_path,
            args='--skip-existing',
        )
        self.assertIn('No files eligible for upload', proc.stdout)

    def test_upload_with_checksumtype(self):
        """Create a repository and upload DRPMs into it.

        Specifically, do the following:

        1. Create a yum repository.
        2. Download a DRPM file.
        3. Upload the DRPM into it specifying the checksumtype
        4. Use ``pulp-admin`` to verify its presence
           in the repository.
        """
        if selectors.bug_is_untestable(2627, config.get_config().version):
            self.skipTest('https://pulp.plan.io/issues/2627')

        # Create a repository
        repo_id = utils.uuid4()
        self.create_repo('rpm', repo_id)
        drpm_file_path = self.temp_download(DRPM_UNSIGNED_URL, DRPM)

        # Upload the DRPM into the repository. Don't use subTest, as if this
        # test fails, the following one is invalid anyway.
        self.upload_to_repo(
            plugin='rpm',
            filetype='drpm',
            repo_id=repo_id,
            filename=drpm_file_path,
            args='--checksum-type sha256',
        )
        self.check_field(
            plugin='rpm',
            filetype='drpm',
            repo_id=repo_id,
            expected=DRPM,
            search_field='filename'
        )


class UploadRPMTestCase(_BaseCLIDownloadTestCase):
    """Test whether one can upload a RPM into a repository."""

    def test_with_vendor(self):
        """Create a repository and upload an RPM with a vendor into it.

        Specifically, do the following:

        1. Create a yum repository.
        2. Download a RPM file.
        3. Upload the RPM into it.
        4. Verify its presence in the repository
        5. Verify the vendor information is intact


        Targets `Pulp Smash #680
        <https://github.com/PulpQE/pulp-smash/issues/680>`_
        """
        if selectors.bug_is_untestable(2781, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2781')

        # Create a repository
        repo_id = utils.uuid4()
        self.create_repo('rpm', repo_id)
        rpm_file_path = self.temp_download(
            RPM_WITH_VENDOR_URL,
            RPM_WITH_VENDOR
        )

        # Upload the RPM into the repository.
        self.upload_to_repo(
            plugin='rpm',
            filetype='rpm',
            repo_id=repo_id,
            filename=rpm_file_path
        )
        # Search for filename in repo to confirm upload
        self.check_field(
            plugin='rpm',
            filetype='rpm',
            repo_id=repo_id,
            expected=RPM_WITH_VENDOR,
            search_field='filename'
        )

        # Check for vendor data
        for word in RPM_WITH_VENDOR_DATA['metadata']['vendor'].split():
            self.check_field(
                plugin='rpm',
                filetype='rpm',
                repo_id=repo_id,
                expected=word,
                search_field='vendor')
