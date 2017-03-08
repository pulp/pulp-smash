# coding=utf-8
"""Tests for copying docker units between repositories."""
import re
import unittest

from packaging.version import Version

from pulp_smash import config, selectors, utils
from pulp_smash.constants import DOCKER_V1_FEED_URL, DOCKER_V2_FEED_URL
from pulp_smash.tests.docker.cli import utils as docker_utils
from pulp_smash.tests.docker.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_IMAGE_ID_RE = r'(?:Image Id:)\s*(.*)'
_NAME_RE = r'(?:Name:)\s*(.*)'
_UNIT_ID_RE = r'(?:Unit Id:)\s*(.*)'
_UPSTREAM_NAME = 'library/busybox'


def _get_unit_ids(server_config, repo_id, unit_type, regex):
    """Search for content units in a docker repository and return their IDs.

    This method is highly specific to the tests in this module, and the best
    way to understand it is to read its source code.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp server being targeted.
    :param repo_id: A docker repository ID.
    :param unit_type: A type of docker content unit, like "image" or "tag."
    :param regex: A regex for searching stdout for unit IDs.
    :returns: A set of unit IDs.
    """
    # We omit `--fields unit_ids` due to https://pulp.plan.io/issues/1693
    units = docker_utils.repo_search(
        server_config,
        repo_id=repo_id,
        unit_type=unit_type,
    ).stdout
    return set(re.findall(regex, units))


class _BaseTestCase(unittest.TestCase):
    """Provides common set-up and tear-down behaviour."""

    @classmethod
    def setUpClass(cls):
        """Perform a variety of set-up tasks.

        Provide a server config, and skip tests if the targeted Pulp system is
        older than version 2.8. Provide a tuple of two repository IDs (See
        :meth:`tearDownClass`.) Log in to the target system.
        """
        cls.cfg = config.get_config()
        if cls.cfg.version < Version('2.8'):
            raise unittest.SkipTest('These tests require Pulp 2.8 or above.')
        utils.pulp_admin_login(cls.cfg)
        cls.repo_ids = tuple((utils.uuid4() for _ in range(2)))

    @classmethod
    def tearDownClass(cls):
        """Destroy each docker repository identified by ``cls.repo_ids``."""
        for repo_id in cls.repo_ids:
            docker_utils.repo_delete(cls.cfg, repo_id)


class _CopyMixin(object):
    """Provides assertions about ``self.copy``.

    This attribute should be a :class:`pulp_smash.cli.CompletedProcess`.
    """

    def test_has_copied(self):
        """Assert "Copied" appears in ``self.copy.stdout``."""
        self.assertIn('Copied', self.copy.stdout)

    def test_not_task_failed(self):
        """Assert "Task Failed" is not in ``self.copy.stdout``."""
        self.assertNotIn('Task Failed', self.copy.stdout)


class CopyAllImagesTestCase(_BaseTestCase, _CopyMixin):
    """Test copying all images from one repository to another."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v1 registry."""
        super(CopyAllImagesTestCase, cls).setUpClass()

        # Create a pair of repositories.
        docker_utils.repo_create(
            cls.cfg,
            enable_v1='true',
            enable_v2='false',
            feed=DOCKER_V1_FEED_URL,
            repo_id=cls.repo_ids[0],
            upstream_name=_UPSTREAM_NAME,
        )
        docker_utils.repo_create(cls.cfg, repo_id=cls.repo_ids[1])

        # Sync the first and copy some content units to the second.
        docker_utils.repo_sync(cls.cfg, cls.repo_ids[0])
        cls.copy = docker_utils.repo_copy(
            cls.cfg,
            unit_type='image',
            from_repo_id=cls.repo_ids[0],
            to_repo_id=cls.repo_ids[1],
        )

    def test_positive_copy_output(self):
        """Assert that the list of image_ids in the copy output are correct."""
        # We pass --fields to work around pulp-admin's weird line breaking
        # behaviour. See: https://pulp.plan.io/issues/1696
        units_in_src = docker_utils.repo_search(
            self.cfg,
            fields='image_id',
            repo_id=self.repo_ids[0],
            unit_type='image',
        ).stdout
        image_ids_search = set(re.findall(_IMAGE_ID_RE, units_in_src))
        image_ids_copy = set(re.findall(r'(?: {2})(\w*)', self.copy.stdout))
        self.assertEqual(image_ids_search, image_ids_copy)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        src_unit_ids, dest_unit_ids = [
            _get_unit_ids(self.cfg, repo_id, 'image', _UNIT_ID_RE)
            for repo_id in self.repo_ids
        ]
        self.assertEqual(src_unit_ids, dest_unit_ids)


class CopyAllManifestsTestCase(_BaseTestCase, _CopyMixin):
    """Test copying all manifests from one repository to another."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry."""
        super(CopyAllManifestsTestCase, cls).setUpClass()
        if (cls.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1909, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1909')

        # Create a pair of repositories.
        docker_utils.repo_create(
            cls.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_ids[0],
            upstream_name=_UPSTREAM_NAME,
        )
        docker_utils.repo_create(cls.cfg, repo_id=cls.repo_ids[1])

        # Sync the first and copy some content units to the second.
        docker_utils.repo_sync(cls.cfg, cls.repo_ids[0])
        cls.copy = docker_utils.repo_copy(
            cls.cfg,
            unit_type='manifest',
            from_repo_id=cls.repo_ids[0],
            to_repo_id=cls.repo_ids[1],
        )

    def test_positive_copy_output(self):
        """Verify the ``pulp-admin docker repo copy`` stdout looks correct.

        Assert that stdout references the correct number of manifests.
        """
        proc = docker_utils.repo_search(
            self.cfg,
            fields='digest',
            repo_id=self.repo_ids[0],
            unit_type='manifest',
        )
        n_search_digests = len(re.findall('Digest: ', proc.stdout))

        # Before Pulp 2.13, stdout is in this form:
        #
        #     Copied:
        #      docker_blob:
        #       sha256:082340653daf0364a24268c6ca0594f22766a683b3e17f49028ef564b229e835
        #       …
        #      docker_manifest:
        #       sha256:01cecc256987d4305fb0b72df9df8440441c4da17036f63c85d5fa89399df53d
        #       …
        #
        # Starting with Pulp 2.13, stdout is more concise:
        #
        #     Copied:
        #       docker_blob: 45
        #       docker_manifest: 75
        #
        if self.cfg.version < Version('2.13'):
            n_copy_digests = self.copy.stdout.split('docker_manifest:')[1]
            n_copy_digests = len(re.findall(r'  (\w*:\w*)', n_copy_digests))
        else:
            n_copy_digests = int(re.search(
                r'docker_manifest: (\d+)',
                self.copy.stdout
            ).group(1))

        self.assertEqual(n_search_digests, n_copy_digests)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        src_unit_ids, dest_unit_ids = [
            _get_unit_ids(self.cfg, repo_id, 'manifest', _UNIT_ID_RE)
            for repo_id in self.repo_ids
        ]
        self.assertEqual(src_unit_ids, dest_unit_ids)


class CopyAllTagsTestCase(_BaseTestCase, _CopyMixin):
    """Test copying all Tags from one repository to another."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry."""
        super(CopyAllTagsTestCase, cls).setUpClass()
        if (cls.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1909, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1909')

        # Create a pair of repositories.
        docker_utils.repo_create(
            cls.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_ids[0],
            upstream_name=_UPSTREAM_NAME,
        )
        docker_utils.repo_create(cls.cfg, repo_id=cls.repo_ids[1])

        # Sync the first and copy some content units to the second.
        docker_utils.repo_sync(cls.cfg, cls.repo_ids[0])
        cls.copy = docker_utils.repo_copy(
            cls.cfg,
            unit_type='tag',
            from_repo_id=cls.repo_ids[0],
            to_repo_id=cls.repo_ids[1],
        )

    def test_positive_copy_output(self):
        """Assert that the list of tags in the copy output are correct."""
        # Sample output:
        #
        #     Copied:
        #       docker_blob: 20
        #       docker_tag: 43
        #       docker_manifest: 43
        #
        copy_count = self.copy.stdout.splitlines()
        copy_count = [line for line in copy_count if 'docker_tag:' in line]
        self.assertEqual(len(copy_count), 1, self.copy.stdout)
        copy_count = int(copy_count[0].split('docker_tag:')[1].strip())

        # Sample output: (Notice "Manifest Digest," not "Digest.")
        #
        #     Created:      2016-10-10T20:45:06Z
        #     Metadata:
        #       Manifest Digest:    sha256:98a0bd48d22ff96ca23bfda2fe1cf72034e…
        #                           274aca0f9c51c
        #       Name:               latest
        #       Pulp User Metadata:
        #       Repo Id:            6d49614e-621a-4a7c-ae0b-ae3885463227
        #     Repo Id:      6d49614e-621a-4a7c-ae0b-ae3885463227
        #     Unit Id:      f0e4abc1-e63f-4e24-a249-8e5b91446787
        #     Unit Type Id: docker_tag
        #     Updated:      2016-10-10T20:45:06Z
        #
        search_count = docker_utils.repo_search(
            self.cfg,
            repo_id=self.repo_ids[0],
            unit_type='tag',
        ).stdout
        search_count = len(re.findall(_UNIT_ID_RE, search_count))

        self.assertEqual(copy_count, search_count)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        for unit_type in {'manifest', 'tag'}:
            with self.subTest(unit_type=unit_type):
                src_unit_ids, dest_unit_ids = [
                    _get_unit_ids(self.cfg, repo_id, unit_type, _NAME_RE)
                    for repo_id in self.repo_ids
                ]
                self.assertEqual(src_unit_ids, dest_unit_ids)
