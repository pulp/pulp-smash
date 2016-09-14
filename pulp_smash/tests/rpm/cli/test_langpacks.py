# coding=utf-8
"""Tests for Pulp's langpack support."""
import unittest

from packaging.version import Version

from pulp_smash import cli, config, utils
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.rpm.cli.utils import count_langpacks


class UploadAndRemoveLangpacksTestCase(unittest.TestCase):
    """Test whether one can upload to and remove langpacks from a repository.

    This test targets `Pulp Smash #270`_. The test steps are as follows:

    1. Create a repository.
    2. Upload langpacks to the repository. Verify the correct number of
       langpacks are present.
    3. Remove langpacks from the repository. Verify that no langpacks are
       present.

    .. _Pulp Smash #270: https://github.com/PulpQE/pulp-smash/issues/270
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        cls.cfg = config.get_config()
        if cls.cfg.version < Version('2.9'):
            raise unittest.SkipTest('This test requires Pulp 2.9 or greater.')
        cls.client = cli.Client(cls.cfg)
        cls.repo_id = utils.uuid4()
        cls.client.run(
            'pulp-admin rpm repo create --repo-id {}'
            .format(cls.repo_id).split()
        )

    def test_01_upload_langpacks(self):
        """Upload a langpack to the repository."""
        cmd = (
            'pulp-admin rpm repo uploads langpacks --repo-id {0} '
            '--name {1} --install {1}-%s'
        ).format(self.repo_id, utils.uuid4()).split()
        self.client.run(cmd)
        num_langpacks = count_langpacks(self.cfg, self.repo_id)
        self.assertEqual(num_langpacks, 1, cmd)

    def test_02_remove_langpacks(self):
        """Remove all langpacks from the repository."""
        cmd = (
            'pulp-admin rpm repo remove langpacks --repo-id {0} '
            '--str-eq repo_id={0}'
        ).format(self.repo_id).split()
        self.client.run(cmd)
        package_counts = count_langpacks(self.cfg, self.repo_id)
        self.assertEqual(package_counts, 0, cmd)

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
