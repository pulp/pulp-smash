# coding=utf-8
"""Test the `retain_old_count`_ feature.

When more than one version of an RPM is present in a repository and Pulp syncs
from that repository, it must choose how many versions of that RPM to sync. By
default, it syncs all versions of that RPM. The `retain_old_count`_ option lets
one sync a limited number of outdated RPMs.

.. _retain_old_count:
    https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html
"""
import re
import unittest
from urllib.parse import urljoin

from pulp_smash import cli, config, utils
from pulp_smash.constants import RPM_UNSIGNED_FEED_URL
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class RetainOldCountTestCase(unittest.TestCase):
    """Test the ``retain_old_count`` feature.

    This test targets `Pulp #2785 <https://pulp.plan.io/issues/2785>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create, populate and publish a repository.

        Ensure at least two versions of an RPM are present in the repository.
        """
        cls.cfg = config.get_config()
        cls.repo_id = None
        cls.relative_url = utils.uuid4() + '/'
        utils.pulp_admin_login(cls.cfg)
        client = cli.Client(cls.cfg)
        repo_id = utils.uuid4()
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id,
            '--feed', RPM_UNSIGNED_FEED_URL, '--relative-url', cls.relative_url
        ))
        cls.repo_id = repo_id
        del repo_id
        try:
            client.run((
                'pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id',
                cls.repo_id
            ))
            cls.content = client.run((
                'pulp-admin', 'rpm', 'repo', 'content', 'rpm', '--repo-id',
                cls.repo_id
            )).stdout
        except:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        """Destroy the repository created by :meth:`setUpClass`."""
        if cls.repo_id:
            cli.Client(cls.cfg).run((
                'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', cls.repo_id
            ))

    def test_retain_zero(self):
        """Give ``retain_old_count`` a value of zero.

        Create a repository whose feed references the repository created by
        :meth:`setUpClass`, and whose ``retain_old_count`` option is zero.
        Sync the repository, and assert that zero old versions of any duplicate
        RPMs were copied over.
        """
        content = self.create_sync_repo(0)
        matcher = re.compile(r'^Name:\s+walrus$', re.MULTILINE)
        matches = [matcher.findall(_) for _ in (self.content, content)]
        self.assertEqual(len(matches[0]) - 1, len(matches[1]))

    def test_retain_one(self):
        """Give ``retain_old_count`` a value of one.

        Create a repository whose feed references the repository created in
        :meth:`setUpClass`, and whose ``retain_old_count`` option is one. Sync
        the repository, and assert that one old version of any duplicate RPMs
        were copied over.
        """
        content = self.create_sync_repo(1)
        matcher = re.compile(r'^Name:\s+walrus$', re.MULTILINE)
        matches = [matcher.findall(_) for _ in (self.content, content)]
        self.assertEqual(len(matches[0]), len(matches[1]))

    def create_sync_repo(self, retain_old_count):
        """Create and sync a repository. Return information about it.

        Implement the logic described by the ``test_retain_*`` methods.
        """
        client = cli.Client(self.cfg)
        repo_id = utils.uuid4()
        feed = urljoin(self.cfg.base_url, 'pulp/repos/' + self.relative_url)
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id,
            '--feed', feed, '--retain-old-count', str(retain_old_count),
        ))
        self.addCleanup(client.run, (
            'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_id,
        ))
        client.run((
            'pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id', repo_id,
        ))
        return client.run((
            'pulp-admin', 'rpm', 'repo', 'content', 'rpm', '--repo-id', repo_id
        )).stdout
