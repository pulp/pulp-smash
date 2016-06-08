# coding=utf-8
"""Tests that perform langpacks upload and removal."""
from __future__ import unicode_literals

import unittest2

from pulp_smash import cli, config, utils
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _count_langpacks(server_config, repo_id):
    """Tell how many package langpacks are in a repository.

    :param server_config: pulp_smash.config.ServerConfig server_config:
        Information about the Pulp server being targeted.
    :param repo_id: A RPM repository ID.
    :returns: The number of package langpacks in a repository, as an ``int``.
    """
    keyword = 'Package Langpacks:'
    completed_proc = cli.Client(server_config).run((
        'pulp-admin repo list --repo-id {} '
        '--fields content_unit_counts'
    ).format(repo_id).split())
    lines = [
        line for line in completed_proc.stdout.splitlines()
        if keyword in line
    ]
    assert len(lines) in (0, 1)
    if len(lines) == 0:
        return 0
    else:
        return int(lines[0].split(keyword)[1].strip())


class UploadAndRemoveLangpacksTestCase(unittest2.TestCase):
    """Upload langpacks and remove it through pulp-rpm.

    This test targets `Pulp Smash #270`_. The test steps would be as follows:

    1. upload langpacks to repo1
    2. check whether the langpacks are really uploaded
    3. remove all langpacks from repo1
    4. check whether the langpacks are actually removed

    .. _Pulp Smash #270: https://github.com/PulpQE/pulp-smash/issues/270
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        cls.cfg = config.get_config()
        cls.client = cli.Client(cls.cfg)
        cls.repo_id = utils.uuid4()
        cls.client.run(
            'pulp-admin rpm repo create --repo-id {}'
            .format(cls.repo_id).split()
        )

    def test_01_upload_langpacks(self):
        """Upload langpacks through pulp-rpm."""
        # SubTest to upload langpacks into the repository
        cmd = (
            'pulp-admin rpm repo uploads langpacks -i hyphen '
            '-n hyphen-%s --repo-id {}'
        ).format(self.repo_id)
        self.client.run(cmd.split())
        package_counts = _count_langpacks(
            self.cfg,
            self.repo_id
        )
        self.assertGreater(package_counts, 0, 'Langpacks are not uploaded')

    def test_02_remove_langpacks(self):
        """Remove langpacks through pulp-rpm."""
        # SubTest to remove all langpacks from the repository
        cmd = (
            'pulp-admin rpm repo remove langpacks --repo-id {0} '
            '--str-eq repo_id={0}'
        ).format(self.repo_id)
        self.client.run(cmd.split())
        package_counts = _count_langpacks(
            self.cfg,
            self.repo_id
        )
        self.assertEqual(package_counts, 0, 'Langpacks are not removed')

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
