# coding=utf-8
"""Tests for Pulp's character encoding handling.

RPM files have metadata embedded in their headers. This metadata should be
encoded as utf-8, and Pulp should gracefully handle cases where invalid byte
sequences are encountered.
"""
import unittest

from pulp_smash import cli, config, selectors, utils
from pulp_smash.constants import RPM_WITH_NON_ASCII_URL, RPM_WITH_NON_UTF_8_URL
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login``."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


class UploadNonAsciiTestCase(unittest.TestCase):
    """Test whether one can upload an RPM with non-ascii metadata.

    Specifically, do the following:

    1. Create an RPM repository.
    2. Upload and import :data:`pulp_smash.constants.RPM_WITH_NON_ASCII_URL`
       into the repository.
    """

    def test_all(self):
        """Test whether one can upload an RPM with non-ascii metadata."""
        cfg = config.get_config()
        client = cli.Client(cfg)

        # Get the RPM
        rpm = client.run(('mktemp',)).stdout.strip()
        self.addCleanup(client.run, ('rm', rpm))
        client.run(('curl', '--output', rpm, RPM_WITH_NON_ASCII_URL))

        # Create a repo.
        repo_id = utils.uuid4()
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id
        ))
        self.addCleanup(
            client.run,
            ('pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_id)
        )

        # Upload an RPM.
        response = client.run((
            'pulp-admin', 'rpm', 'repo', 'uploads', 'rpm', '--repo-id',
            repo_id, '--file', rpm
        ))
        for stream in (response.stdout, response.stderr):
            self.assertNotIn('Task Failed', stream)


class UploadNonUtf8TestCase(unittest.TestCase):
    """Test whether one can upload an RPM with non-utf-8 metadata.

    Specifically, do the following:

    1. Create an RPM repository.
    2. Upload and import :data:`pulp_smash.constants.RPM_WITH_NON_UTF_8_URL`
       into the repository.

    This test case targets `Pulp #1903 <https://pulp.plan.io/issues/1903>`_.
    """

    def test_all(self):
        """Test whether one can upload an RPM with non-utf-8 metadata."""
        cfg = config.get_config()
        if selectors.bug_is_untestable(1903, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1903')
        client = cli.Client(cfg)

        # Get the RPM
        rpm = client.run(('mktemp',)).stdout.strip()
        self.addCleanup(client.run, ('rm', rpm))
        client.run(('curl', '--output', rpm, RPM_WITH_NON_UTF_8_URL))

        # Create a repo.
        repo_id = utils.uuid4()
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id
        ))
        self.addCleanup(
            client.run,
            ('pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_id)
        )

        # Upload an RPM.
        response = client.run((
            'pulp-admin', 'rpm', 'repo', 'uploads', 'rpm', '--repo-id',
            repo_id, '--file', rpm
        ))
        for stream in (response.stdout, response.stderr):
            self.assertNotIn('Task Failed', stream)
