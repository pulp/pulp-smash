# coding=utf-8
"""Tests for RPM package environments."""
from __future__ import unicode_literals

import subprocess
import unittest2

from pulp_smash import cli, config, utils
from pulp_smash.constants import RPM_FEED_URL


class UploadPackageEnvTestCase(unittest2.TestCase):
    """Test whether Pulp can upload package environments into a repository.

    This test case covers `Pulp #1003`_ and the corresponding Pulp Smash
    issue `Pulp Smash #319`_. The following test steps are based on official
    `Pulp RPM Recipes`_.

    1. Create and sync a repository.
    2. Upload the environmrnt into this repo and check if there's any error.

    .. _Pulp #1003: https://pulp.plan.io/issues/1003
    .. _Pulp Smash #319: https://github.com/PulpQE/pulp-smash/issues/319
    .. _Pulp RPM Recipes: http://docs.pulpproject.org/plugins/pulp_rpm/
            user-guide/recipes.html#create-your-own-package-environment
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository."""
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        cls.client = cli.Client(cls.cfg)
        cls.client.run(
            'pulp-admin rpm repo create --repo-id {} --feed {}'
            .format(cls.repo_id, RPM_FEED_URL).split()
        )
        try:
            cls.client.run(
                'pulp-admin rpm repo sync run --repo-id {}'
                .format(cls.repo_id).split()
            )
        except subprocess.CalledProcessError:
            cls.client.run(
                'pulp-admin rpm repo delete --repo-id {}'
                .format(cls.repo_id).split()
            )
            raise

    @classmethod
    def tearDownClass(cls):
        """Destroy the repository."""
        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )

    def test_upload_environment(self):
        """Test if package environments can be uploaded."""
        rpm_env_name = 'Pulp Test Packages'
        rpm_env_desc = 'A package environment of Pulp tests.'
        proc_upload = self.client.machine.session().run(
            'pulp-admin rpm repo uploads environment '
            '--repo-id {0} --environment-id {1} '
            '--name "{2}" --description "{3}"'
            .format(self.repo_id, utils.uuid4(), rpm_env_name, rpm_env_desc)
        )
        with self.subTest(comment='verify upload environments stdout'):
            self.assertNotIn('Task Failed', proc_upload[1])
        proc_content = self.client.run(
            'pulp-admin rpm repo content environment --repo-id {}'
            .format(self.repo_id).split()
        )
        for expected in (rpm_env_name, rpm_env_desc):
            with self.subTest():
                self.assertIn(expected, proc_content.stdout)
