# coding=utf-8
"""Tests upload of units via client."""
from __future__ import unicode_literals

import os

import unittest2

from pulp_smash import cli, config, utils, selectors
from pulp_smash.constants import DRPM_URL, DRPM
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login`` on the target Pulp system."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


class UploadDrpmTestCase(unittest2.TestCase):
    """Test whether one can upload DRPMs."""

    @classmethod
    def setUpClass(cls):
        """Create a repository and download temporary drpm."""
        super(UploadDrpmTestCase, cls).setUpClass()

        cls.cfg = config.get_config()

        if selectors.bug_is_untestable(1806, cls.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1806')

        cls.repo_id = utils.uuid4()
        cls.client = cli.Client(cls.cfg)

        cls.client.run(
            'pulp-admin rpm repo create --repo-id {}'
            .format(cls.repo_id).split()
        )

        completed_process = cls.client.run(
            'mktemp --directory'.split()
        )
        cls.temp_folder = completed_process.stdout.strip()
        cls.temp_drpm = os.path.join(cls.temp_folder, DRPM)

        cls.client.run(
            'curl -o {} {}'
            .format(cls.temp_drpm, DRPM_URL).split()
        )

    @classmethod
    def tearDownClass(cls):
        """Delete the repository and drpm created by :meth:`setUpClass`."""
        super(UploadDrpmTestCase, cls).tearDownClass()

        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
        cls.client.run('pulp-admin orphan remove --all'.split())
        cls.client.run('rm -rf {}'.format(cls.temp_folder).split())

    def test_upload_and_output(self):
        """Test upload of DRPM.

        Steps

        1. Upload DRPM
        2. Check output of ``pulp-admin rpm repo content drpm``

        This test case targets
        `Pulp Smash #336 <https://github.com/PulpQE/pulp-smash/issues/336>`_
        """
        self.client.run(
            'pulp-admin rpm repo uploads drpm --repo-id {} -f {}'
            .format(self.repo_id, self.temp_drpm).split()
        )
        completed_process = self.client.run(
            'pulp-admin rpm repo content drpm --repo-id {} --fields filename'
            .format(self.repo_id).split()
        )

        filename = completed_process.stdout.split('Filename:')[1].strip()

        self.assertEqual(filename, 'drpms/' + DRPM)

    def test_upload_skip_existing(self):
        """Test duplicit upload of DRPM with flag ``--skip-existing``.

        Steps

        1. Upload DRPM
        2. Upload again with flag and check if it wasn't uploaded.

        This test case targets
        `Pulp Smash #336 <https://github.com/PulpQE/pulp-smash/issues/336>`_
        """
        self.client.run(
            'pulp-admin rpm repo uploads drpm --repo-id {} -f {}'
            .format(self.repo_id, self.temp_drpm).split()
        )
        completed_process = self.client.run(
            ('pulp-admin rpm repo uploads drpm --repo-id {} -f {} '
             '--skip-existing')
            .format(self.repo_id, self.temp_drpm).split()
        )

        self.assertIn('No files eligible for upload', completed_process.stdout)
