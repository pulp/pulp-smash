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
from pulp_smash.tests.rpm.utils import check_issue_2277
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class RetainOldCountTestCase(unittest.TestCase):
    """Test the ``retain_old_count`` feature."""

    def test_all(self):
        """Test the ``retain_old_count`` feature.

        Specifically, do the following:

        1. Create, populate and publish repository. Ensure at least two
           versions of some RPM are present.
        2. Create and sync a second repository whose feed references the first
           repository and where ``retain_old_count`` is zero.
        3. Inspect the two repositories. Assert that only the newest version of
           any duplicate RPMs has been copied to the second repository.
        """
        cfg = config.get_config()
        if check_issue_2277(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        utils.pulp_admin_login(cfg)
        repo_ids = tuple(utils.uuid4() for _ in range(2))
        relative_url = utils.uuid4() + '/'
        client = cli.Client(cfg)

        # Create, populate and publish a repo.
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_ids[0],
            '--feed', RPM_UNSIGNED_FEED_URL, '--relative-url', relative_url
        ))
        self.addCleanup(client.run, (
            'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_ids[0],
        ))
        client.run((
            'pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id',
            repo_ids[0]
        ))

        # Create and sync a second repository.
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create',
            '--repo-id', repo_ids[1],
            '--feed', urljoin(cfg.base_url, 'pulp/repos/' + relative_url),
            '--retain-old-count', '0',
        ))
        self.addCleanup(client.run, (
            'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_ids[1],
        ))
        client.run((
            'pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id',
            repo_ids[1],
        ))

        # Inspect the repos. Most of the RPMs in the first repo are unique.
        # However, there are two versions of the "walrus" RPM, and when
        # ``retain_old_count=0``, zero old versions should be copied over.
        contents = [
            client.run((
                'pulp-admin', 'rpm', 'repo', 'content', 'rpm', '--repo-id',
                repo_id
            )).stdout
            for repo_id in repo_ids
        ]
        matcher = re.compile(r'^Name:\s+walrus$', re.MULTILINE)
        matches = [matcher.findall(content) for content in contents]
        self.assertEqual(len(matches[0]) - 1, len(matches[1]))
