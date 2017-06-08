# coding=utf-8
"""Tests that work with tags on docker repositories."""
import hashlib
import random
import unittest
import uuid
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, utils
from pulp_smash.constants import (
    CONTENT_UPLOAD_PATH,
    DOCKER_UPSTREAM_NAME,
    DOCKER_V1_FEED_URL,
    DOCKER_V2_FEED_URL,
    REPOSITORY_PATH,
)
from pulp_smash.exceptions import TaskReportError
from pulp_smash.tests.docker.api_v2.utils import gen_repo
from pulp_smash.tests.docker.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests on Pulp versions lower than 2.12."""
    set_up_module()
    if config.get_config().version < Version('2.12'):
        raise unittest.SkipTest('These tests require at least Pulp 2.12.')


def create_docker_repo(cfg, upstream_name, use_v1=False):
    """Create a docker repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param upstream_name: The Docker container upstream name.
    :param use_v1: If ``True`` use Docker V1 feed URL else use Docker V2 feed
        URL.
    :return: Detailed information about the created repository.
    """
    body = gen_repo()
    if use_v1:
        body['importer_config'].update({
            'enable_v1': True,
            'feed': DOCKER_V1_FEED_URL,
        })
    else:
        body['importer_config'].update({
            'feed': DOCKER_V2_FEED_URL,
        })
    body['importer_config']['upstream_name'] = upstream_name
    client = api.Client(cfg, api.json_handler)
    return client.post(REPOSITORY_PATH, body)


def import_upload(cfg, repo, params):
    """Create or update a docker repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param repo: A dict of information about the targed repository.
    :param params: A dict of information to pass as import_upload body.
    :return: A dict of information about the creation/update report.
    """
    client = api.Client(cfg, api.json_handler)
    malloc = client.post(CONTENT_UPLOAD_PATH)
    body = {'unit_key': {}, 'upload_id': malloc['upload_id']}
    body.update(params)
    report = client.post(
        urljoin(repo['_href'], 'actions/import_upload/'), body)
    client.delete(malloc['_href'])
    return report


class DockerTagTestCase(utils.BaseAPITestCase):
    """Tests for docker repository tagging feature."""

    def setUp(self):
        """Create and sync a docker repository."""
        super().setUp()
        self.repo = create_docker_repo(self.cfg, DOCKER_UPSTREAM_NAME)
        self.addCleanup(api.Client(self.cfg).delete, self.repo['_href'])
        utils.sync_repo(self.cfg, self.repo)
        self.repo = api.Client(self.cfg, api.json_handler).get(
            self.repo['_href'], params={'details': True})
        self.tags = self._get_tags()

    def _get_tags(self):
        return utils.search_units(
            self.cfg,
            self.repo,
            {'type_ids': ['docker_tag']},
        )

    def test_create_tag(self):
        """Check if a tag can be created."""
        tag_name = str(uuid.uuid4())
        random_manifest = random.choice(utils.search_units(
            self.cfg, self.repo, {'type_ids': ['docker_manifest']}))
        # Create the tag
        import_upload(self.cfg, self.repo, {
            'unit_type_id': 'docker_tag',
            'unit_key': {
                'repo_id': self.repo['id'],
                'name': tag_name,
            },
            'unit_metadata': {
                'name': tag_name,
                'digest': random_manifest['metadata']['digest'],
            },
        })
        # Fetch the created tag
        tag = utils.search_units(self.cfg, self.repo, {
            'type_ids': ['docker_tag'],
            'filters': {'unit': {'name': tag_name}},
        })
        self.assertEqual(len(tag), 1)
        tag = tag.pop()
        self.assertEqual(
            tag['metadata']['manifest_digest'],
            random_manifest['metadata']['digest']
        )
        self.assertEqual(len(self._get_tags()), len(self.tags) + 1)

    def test_update_tag(self):
        """Check if a tag can be updated to a new manifest.

        Do the following:

        1. Find the tag in this test's docker repository whose name is
           "latest." Make note of the manifest it references.
        2. Pick some other manifest. Update the repository so that the "latest"
           tag references the chosen manifest.
        3. Find the tag in this test's docker repository whose name is
           "latest." Assert it references the chosen manifest.
        """
        # Find the "latest" tag.
        tag = self.get_latest_tags()
        self.assertEqual(len(tag), 1)
        tag = tag.pop()

        # Find the manifest the "latest" tag references.
        old_manifest = utils.search_units(self.cfg, self.repo, {
            'type_ids': ['docker_manifest'],
            'filters': {
                'unit': {'digest': tag['metadata']['manifest_digest']}
            },
        })
        self.assertEqual(len(old_manifest), 1)
        old_manifest = old_manifest.pop()

        # Pick a new manifest.
        manifests = self.get_manifests()
        manifests.remove(old_manifest)
        new_manifest = random.choice(manifests)

        # Make the "latest" tag reference the new manifest.
        import_upload(self.cfg, self.repo, {
            # Identify the tag being updated...
            'unit_key': {
                'name': tag['metadata']['name'],
                'repo_id': tag['metadata']['repo_id'],
            },
            'unit_type_id': 'docker_tag',
            # ...and provide changed attributes.
            'unit_metadata': {
                'digest': new_manifest['metadata']['digest'],
                'name': tag['metadata']['name'],
            },
        })

        # Find the "latest" tag.
        tag = self.get_latest_tags()
        self.assertEqual(len(tag), 1)
        tag = tag.pop()

        # Assert the tag references the correct manifest.
        tag_digest = tag['metadata']['manifest_digest']
        with self.subTest():
            self.assertNotEqual(tag_digest, old_manifest['metadata']['digest'])
        with self.subTest():
            self.assertEqual(tag_digest, new_manifest['metadata']['digest'])

    def test_update_tag_invalid_manifest(self):  # pylint:disable=invalid-name
        """Check if tagging fail for a invalid manifest."""
        tag_name = str(uuid.uuid4())
        manifest_digest = 'sha256:{}'.format(hashlib.sha256(
            bytes(str(uuid.uuid4()), encoding='utf-8')).hexdigest())
        # Create the tag
        with self.assertRaises(TaskReportError) as context:
            import_upload(self.cfg, self.repo, {
                'unit_type_id': 'docker_tag',
                'unit_key': {
                    'repo_id': self.repo['id'],
                    'name': tag_name,
                },
                'unit_metadata': {
                    'name': tag_name,
                    'digest': manifest_digest,
                },
            })
        self.assertEqual(
            'Manifest with digest {} could not be found in repository {}.'
            .format(manifest_digest, self.repo['id']),
            context.exception.task['error']['description']
        )
        self.assertEqual(len(self._get_tags()), len(self.tags))

    def test_update_tag_another_repo(self):
        """Check if tagging fail for a manifest from another repo."""
        other = create_docker_repo(self.cfg, 'library/swarm')
        self.addCleanup(api.Client(self.cfg).delete, other['_href'])
        utils.sync_repo(self.cfg, other)
        other = api.Client(self.cfg, api.json_handler).get(
            other['_href'], params={'details': True})
        other_manifest = random.choice(utils.search_units(
            self.cfg, other, {'type_ids': ['docker_manifest']}))
        tag_name = str(uuid.uuid4())
        with self.assertRaises(TaskReportError) as context:
            import_upload(self.cfg, self.repo, {
                'unit_type_id': 'docker_tag',
                'unit_key': {
                    'repo_id': self.repo['id'],
                    'name': tag_name,
                },
                'unit_metadata': {
                    'name': tag_name,
                    'digest': other_manifest['metadata']['digest'],
                },
            })
        self.assertEqual(
            'Manifest with digest {} could not be found in repository {}.'
            .format(other_manifest['metadata']['digest'], self.repo['id']),
            context.exception.task['error']['description']
        )
        self.assertEqual(len(self._get_tags()), len(self.tags))

    def get_latest_tags(self):
        """Return all tags in this test's repo with a name of "latest".

        Starting with Pulp 2.13, docker schema v2 is supported. As a result, a
        tag or manifest may be included in search results twice, with a
        differing schema_version. For convenience, if the Pulp system under
        test is version 2.13 or newer, only schema v1 is targeted. (The choice
        of schema version 1 is arbitrary.) See `Pulp #2099
        <https://pulp.plan.io/issues/2099>`_.

        :returns: A list of docker tags.
        """
        criteria = {
            'filters': {'unit': {'name': 'latest'}},
            'type_ids': ['docker_tag'],
        }
        if self.cfg.version >= Version('2.13'):
            criteria['filters']['unit']['schema_version'] = 1
        return utils.search_units(self.cfg, self.repo, criteria)

    def get_manifests(self):
        """Return all manifests in this test's repo.

        If the Pulp system under test is version 2.13 or newer, only return
        schema v1 manifests. See :meth:`get_latest_tags`.
        """
        criteria = {'type_ids': ['docker_manifest']}
        if self.cfg.version >= Version('2.13'):
            criteria['filters'] = {'unit': {'schema_version': 1}}
        return utils.search_units(self.cfg, self.repo, criteria)
