# coding utf-8
"""Test the `retain_old_count`_ feature.

When more than one version of an RPM is present in a repository and Pulp syncs
from that repository, it must choose how many versions of that RPM to sync. By
default, it syncs all versions of that RPM. The `retain_old_count`_ option lets
one sync a limited number of outdated RPMs.

.. _retain_old_count:
    https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html
"""
from urllib.parse import urljoin

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_UNSIGNED_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class RetainOldCountTestCase(utils.BaseAPITestCase):
    """Test the ``retain_old_count`` feature."""

    @classmethod
    def setUpClass(cls):
        """Create, populate and publish a repository.

        Ensure at least two versions of an RPM are present in the repository.
        """
        super().setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        cls.repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(cls.repo['_href'])
        try:
            cls.repo = client.get(cls.repo['_href'], params={'details': True})
            utils.sync_repo(cls.cfg, cls.repo)
            utils.publish_repo(cls.cfg, cls.repo)
            cls.repo = client.get(cls.repo['_href'], params={'details': True})
        except:
            cls.tearDownClass()
            raise

    def test_retain_zero(self):
        """Give ``retain_old_count`` a value of zero.

        Create a repository whose feed references the repository created by
        :meth:`setUpClass`, and whose ``retain_old_count`` option is zero.
        Sync the repository, and assert that zero old versions of any duplicate
        RPMs were copied over.
        """
        repo = self.create_sync_repo(0)
        counts = [_['content_unit_counts']['rpm'] for _ in (self.repo, repo)]
        self.assertEqual(counts[0] - 1, counts[1])

    def test_retain_one(self):
        """Give ``retain_old_count`` a value of one.

        Create a repository whose feed references the repository created in
        :meth:`setUpClass`, and whose ``retain_old_count`` option is one. Sync
        the repository, and assert that one old version of any duplicate RPMs
        were copied over.
        """
        repo = self.create_sync_repo(1)
        counts = [_['content_unit_counts']['rpm'] for _ in (self.repo, repo)]
        self.assertEqual(counts[0], counts[1])

    def create_sync_repo(self, retain_old_count):
        """Create and sync a repository. Return detailed information about it.

        Implement the logic described by the ``test_retain_*`` methods.
        """
        # We disable SSL validation for a practical reason: each HTTPS feed
        # must have a certificate to work, which is burdensome to do here.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = urljoin(
            self.cfg.base_url,
            'pulp/repos/' +
            self.repo['distributors'][0]['config']['relative_url'],
        )
        body['importer_config']['retain_old_count'] = retain_old_count
        body['importer_config']['ssl_validation'] = False
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(self.cfg, repo)
        return client.get(repo['_href'], params={'details': True})
