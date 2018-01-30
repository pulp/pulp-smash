# coding=utf-8
"""Tests for uploading content to docker repositories."""
import unittest

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import DOCKER_V2_FEED_URL
from pulp_smash.tests.pulp2.docker.api_v2.utils import SyncPublishMixin
from pulp_smash.tests.pulp2.docker.utils import (
    set_up_module,
    write_manifest_list,
)


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login``."""
    set_up_module()
    utils.pulp_admin_login(config.get_config())


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

    def setUp(self):
        """Create a docker repository."""
        self.repo = self.create_repo(self.cfg, False, True, DOCKER_V2_FEED_URL)

    @selectors.skip_if(bool, 'repo', False)
    def test_01_upload_manifest_list(self):
        """Test upload of manifest list V2 without perform a sync.

        This test targets the following issues:

        * `Pulp Smash #829 <https://github.com/PulpQE/pulp-smash/issues/829>`_
        * `Pulp #2993 <https://pulp.plan.io/issues/2993>`_

        Do the following:

        1. Create, sync and publish a repository.
        2. Read the manifest list, and remove one of the existent
           architectures from it.
        3. From the modified manifest list create a new JSON valid on a
           temporary dir on disk.
        4. Upload the just created JSON file to the repository.
        5. Assert that the number of ``docker_manifest_list`` present on the
           repository has increased.
        """
        content_type = (
            'application/vnd.docker.distribution.manifest.list.v2+json'
        )
        client = api.Client(
            self.cfg,
            request_kwargs={'headers': {'accept': content_type}}
        )
        client.request_kwargs['url'] = self.adjust_url(
            client.request_kwargs['url']
        )
        response = client.get(
            '/v2/{}/manifests/latest'.format(self.repo['id'])
        )
        manifest_list = response.json()
        # In order to modify the current manifest list, one unwanted
        # architecture is removed.
        manifest_list['manifests'].pop()
        manifest_path, dir_path = write_manifest_list(self.cfg, manifest_list)
        repos = []
        api_client = api.Client(self.cfg, api.json_handler)
        repos.append(api_client.get(self.repo['_href']))
        cli_client = cli.Client(self.cfg)
        self.addCleanup(cli_client.run, ('rm', '-rf', dir_path))
        cli_client.machine.session().run(
            'pulp-admin docker repo uploads upload --repo-id {} -f {}'
            .format(self.repo['id'], manifest_path)
        )
        repos.append(api_client.get(self.repo['_href']))
        self.assertGreater(
            repos[1]['content_unit_counts']['docker_manifest_list'],
            repos[0]['content_unit_counts']['docker_manifest_list']
        )
