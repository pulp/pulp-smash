# coding=utf-8
"""Tests for copying docker units between repositories."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors
from pulp_smash.constants import DOCKER_V1_FEED_URL, DOCKER_V2_FEED_URL
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import sync_repo
from pulp_smash.tests.pulp2.docker.api_v2.utils import gen_repo
from pulp_smash.tests.pulp2.docker.utils import get_upstream_name
from pulp_smash.tests.pulp2.docker.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class CopyV1ContentTestCase(unittest.TestCase):
    """Copy data between Docker repositories with schema v1 content."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        super().setUpClass()
        cls.cfg = config.get_config()
        cls.repo = {}

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        if cls.repo:
            api.Client(cls.cfg).delete(cls.repo['_href'])
        super().tearDownClass()

    def test_01_set_up(self):
        """Create a repository and populate with with schema v1 content."""
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'].update({
            'enable_v1': True,
            'enable_v2': False,
            'feed': DOCKER_V1_FEED_URL,
            'upstream_name': get_upstream_name(self.cfg),
        })
        type(self).repo = client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, self.repo)
        type(self).repo = client.get(
            self.repo['_href'],
            params={'details': True}
        )

    @selectors.skip_if(bool, 'repo', False)
    def test_02_copy_images(self):
        """Copy tags from one repository to another.

        Assert the same number of images are present in both repositories.
        """
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'source_repo_id': self.repo['id'],
            'criteria': {'filters': {}, 'type_ids': ['docker_image']},
        })
        repo = client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_image'],
            repo['content_unit_counts'].get('docker_image', 0),
        )


class CopyV2ContentTestCase(unittest.TestCase):
    """Copy data between Docker repositories with schema v2 content."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        super().setUpClass()
        cls.cfg = config.get_config()
        cls.repo = {}

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        if cls.repo:
            api.Client(cls.cfg).delete(cls.repo['_href'])
        super().tearDownClass()

    def test_01_set_up(self):
        """Create a repository and populate with with schema v2 content."""
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'].update({
            'enable_v1': False,
            'enable_v2': True,
            'feed': DOCKER_V2_FEED_URL,
            'upstream_name': get_upstream_name(self.cfg),
        })
        type(self).repo = client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, self.repo)
        type(self).repo = client.get(
            self.repo['_href'],
            params={'details': True}
        )

    @selectors.skip_if(bool, 'repo', False)
    def test_02_copy_tags(self):
        """Copy tags from one repository to another.

        Assert the same number of tags are present in both repositories.
        """
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'source_repo_id': self.repo['id'],
            'criteria': {'filters': {}, 'type_ids': ['docker_tag']},
        })
        repo = client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_tag'],
            repo['content_unit_counts'].get('docker_tag', 0),
        )

    @selectors.skip_if(bool, 'repo', False)
    def test_02_copy_manifests(self):
        """Copy manifests from one repository to another.

        Assert the same number of manifests are present in both repositories.
        """
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'criteria': {'filters': {}, 'type_ids': ['docker_manifest']},
            'source_repo_id': self.repo['id'],
        })
        repo = client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_manifest'],
            repo['content_unit_counts'].get('docker_manifest', 0),
        )

    @selectors.skip_if(bool, 'repo', False)
    def test_02_copy_manifest_lists(self):
        """Copy manifest lists from one repository to another.

        Assert the same number of manifest lists are present in both
        repositories. This test targets:

        * `Pulp #2384 <https://pulp.plan.io/issues/2384>`_
        * `Pulp #2385 <https://pulp.plan.io/issues/2385>`_
        """
        for issue_id in (2384, 2385):
            if selectors.bug_is_untestable(issue_id, self.cfg.pulp_version):
                self.skipTest(
                    'https://pulp.plan.io/issues/{}'.format(issue_id)
                )
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'criteria': {'filters': {}, 'type_ids': ['docker_manifest_list']},
            'source_repo_id': self.repo['id'],
        })
        repo = client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_manifest_list'],
            repo['content_unit_counts'].get('docker_manifest_list', 0),
        )
