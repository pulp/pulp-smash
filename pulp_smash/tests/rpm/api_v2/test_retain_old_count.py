# coding utf-8
"""Test the `retain_old_count`_ feature.

When more than one version of an RPM is present in a repository and Pulp syncs
from that repository, it must choose how many versions of that RPM to sync. By
default, it syncs all versions of that RPM. The `retain_old_count`_ option lets
one sync a limited number of outdated RPMs.

.. _retain_old_count:
    https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_UNSIGNED_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
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
        client = api.Client(cfg, api.json_handler)

        # Create, populate and publish a repo.
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo['_href'])
        utils.publish_repo(cfg, repo)

        # Create second repository. We disable SSL validation for a practical
        # reason: each HTTPS feed must have a certificate to work, which is
        # burdensome to do here.
        body = gen_repo()
        body['importer_config']['feed'] = urljoin(
            cfg.base_url,
            'pulp/repos/' + repo['distributors'][0]['config']['relative_url'],
        )
        body['importer_config']['retain_old_count'] = 0
        body['importer_config']['ssl_validation'] = False
        repo2 = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo2['_href'])
        utils.sync_repo(cfg, repo2['_href'])

        # Inspect the repos. Most of the RPMs in the first repo are unique.
        # However, there are two versions of the "walrus" RPM, and when
        # ``retain_old_count=0``, zero old versions should be copied over.
        repo = client.get(repo['_href'], params={'details': True})
        repo2 = client.get(repo2['_href'], params={'details': True})
        counts = [repo['content_unit_counts']['rpm'] for repo in (repo, repo2)]
        self.assertEqual(counts[0] - 1, counts[1])
