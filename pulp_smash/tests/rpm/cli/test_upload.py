# coding=utf-8
"""Tests that upload content units into repositories."""
import os
import unittest

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import DRPM, DRPM_UNSIGNED_URL
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login`` on the target Pulp system."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


class UploadDrpmTestCase(unittest.TestCase):
    """Test whether one can upload a DRPM into a repository.

    This test case targets `Pulp Smash #336
    <https://github.com/PulpQE/pulp-smash/issues/336>`_
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
        if selectors.bug_is_untestable(1806, config.get_config().version):
            self.skipTest('https://pulp.plan.io/issues/1806')

        # Create a repository
        client = cli.Client(config.get_config())
        repo_id = utils.uuid4()
        client.run(
            'pulp-admin rpm repo create --repo-id {}'.format(repo_id).split()
        )
        self.addCleanup(
            client.run,
            'pulp-admin rpm repo delete --repo-id {}'.format(repo_id).split()
        )

        # Create a temporary directory, and download a DRPM file into it
        temp_dir = client.run('mktemp --directory'.split()).stdout.strip()
        self.addCleanup(client.run, 'rm -rf {}'.format(temp_dir).split())
        drpm_file = os.path.join(temp_dir, os.path.split(DRPM)[-1])
        client.run(
            'curl -o {} {}'.format(drpm_file, DRPM_UNSIGNED_URL).split()
        )

        # Upload the DRPM into the repository. Don't use subTest, as if this
        # test fails, the following one is invalid anyway.
        client.run(
            'pulp-admin rpm repo uploads drpm --repo-id {} --file {}'
            .format(repo_id, drpm_file).split()
        )
        proc = client.run(
            'pulp-admin rpm repo content drpm --repo-id {} --fields filename'
            .format(repo_id).split()
        )
        self.assertEqual(proc.stdout.split('Filename:')[1].strip(), DRPM)

        # Upload the DRPM into the repository. Pass --skip-existing.
        proc = client.run(
            ('pulp-admin rpm repo uploads drpm --repo-id {} --file {} '
             '--skip-existing')
            .format(repo_id, drpm_file).split()
        )
        self.assertIn('No files eligible for upload', proc.stdout)
