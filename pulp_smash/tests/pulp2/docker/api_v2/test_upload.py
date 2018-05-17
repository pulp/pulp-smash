# coding=utf-8
"""Tests for uploading content to docker repositories."""
import copy
import json
import unittest

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import DOCKER_V2_FEED_URL
from pulp_smash.pulp2.utils import pulp_admin_login, upload_import_unit
from pulp_smash.tests.pulp2.docker.api_v2.utils import SyncPublishMixin
from pulp_smash.tests.pulp2.docker.utils import (
    get_upstream_name,
    set_up_module,
)


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login``."""
    set_up_module()
    pulp_admin_login(config.get_config())


class UploadManifestListV2TestCase(SyncPublishMixin, unittest.TestCase):
    """Test upload of manifest list V2 without perform a sync."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        super().setUpClass()
        cls.cfg = config.get_config()
        if (utils.os_is_f26(cls.cfg) and
                selectors.bug_is_untestable(3036, cls.cfg.pulp_version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/3036')
        for issue_id in (2287, 2384, 2993):
            if selectors.bug_is_untestable(issue_id, cls.cfg.pulp_version):
                raise unittest.SkipTest(
                    'https://pulp.plan.io/issues/{}'.format(issue_id)
                )

    def test_all(self):
        """Upload a V2 manifest list.

        Do the following:

        1. Create, sync and publish a repository. Read the repository and the
           repository's manifest list.
        2. Upload a modified version of the manifest list to the repository.
           Re-read the repository and the repository's manifest list.
        3. Assert that:

           * The repository's manifest list hasn't been changed. (After all,
             the repository hasn't been published since the new manifest list
             was uploaded.)
           * The repository's ``docker_manifest_list`` attribute has increased
             by the approprate number.

        This test targets the following issues:

        * `Pulp #2993 <https://pulp.plan.io/issues/2993>`_
        * `Pulp Smash #829 <https://github.com/PulpQE/pulp-smash/issues/829>`_
        """
        repo = self.create_sync_publish_repo(self.cfg, {
            'enable_v1': False,
            'enable_v2': True,
            'feed': DOCKER_V2_FEED_URL,
            'upstream_name': get_upstream_name(self.cfg),
        })
        crane_client = self.make_crane_client(self.cfg)
        crane_client.request_kwargs['headers']['accept'] = (
            'application/vnd.docker.distribution.manifest.list.v2+json'
        )
        manifest_list_path = '/v2/{}/manifests/latest'.format(repo['id'])
        manifest_list = crane_client.get(manifest_list_path)

        # Upload a modified manifest list.
        modified_manifest_list = copy.deepcopy(manifest_list)
        modified_manifest_list['manifests'].pop()
        upload_import_unit(
            self.cfg,
            json.dumps(modified_manifest_list).encode('utf-8'),
            {'unit_type_id': 'docker_manifest_list'},
            repo,
        )

        # Verify outcomes.
        with self.subTest(comment='verify manifest list is same'):
            new_manifest_list = crane_client.get(manifest_list_path)
            self.assertEqual(manifest_list, new_manifest_list)
        with self.subTest(comment='verify docker_manifest_list repo attr'):
            new_repo = api.Client(self.cfg).get(repo['_href']).json()
            self.assertEqual(
                repo['content_unit_counts']['docker_manifest_list'] +
                len(modified_manifest_list['manifests']),
                new_repo['content_unit_counts']['docker_manifest_list'],
            )
