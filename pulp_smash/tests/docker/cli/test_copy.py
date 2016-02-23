# coding=utf-8
"""Tests for copying docker units between repositories."""
from __future__ import unicode_literals

import re

import unittest2
from packaging.version import Version

from pulp_smash import config, utils
from pulp_smash.constants import DOCKER_V1_FEED_URL, DOCKER_V2_FEED_URL
from pulp_smash.tests.docker.cli import utils as docker_utils

_DIGEST_RE = r'(?:Digest:)\s*(.*)'
_IMAGE_ID_RE = r'(?:Image Id:)\s*(.*)'
_NAME_RE = r'(?:Name:)\s*(.*)'
_UNIT_ID_RE = r'(?:Unit Id:)\s*(.*)'
_UPSTREAM_NAME = 'library/busybox'


def _get_unit_ids(server_config, repo_id, unit_type, regex):
    """Search for content units in a docker repository and return their IDs.

    This method is highly specific to the tests in this module, and the best
    way to understand it is to read its source code.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
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


def _truncate_ids(unit_ids):
    """Drop the last character of each unit ID and return the result as a set.

    pulp-admin hard-wraps search results. This can result in wonky output::

        Metadata:
          Digest: sha256:3e2261c673a3e5284252cf182c5706154471e6548e1b0eb9082c4c
                  c

    An incorrect but easy solution is to use these truncated IDs and truncate
    the other set of IDs too. See: https://pulp.plan.io/issues/1696
    """
    return {unit_id[:-1] for unit_id in unit_ids}


class _BaseTestCase(unittest2.TestCase):
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
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        docker_utils.login(cls.cfg)
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
        docker_utils.repo_create_update(
            cls.cfg,
            enable_v1='true',
            enable_v2='false',
            feed=DOCKER_V1_FEED_URL,
            repo_id=cls.repo_ids[0],
            upstream_name=_UPSTREAM_NAME,
        )
        docker_utils.repo_create_update(cls.cfg, repo_id=cls.repo_ids[1])

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

        # Create a pair of repositories.
        docker_utils.repo_create_update(
            cls.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_ids[0],
            upstream_name=_UPSTREAM_NAME,
        )
        docker_utils.repo_create_update(cls.cfg, repo_id=cls.repo_ids[1])

        # Sync the first and copy some content units to the second.
        docker_utils.repo_sync(cls.cfg, cls.repo_ids[0])
        cls.copy = docker_utils.repo_copy(
            cls.cfg,
            unit_type='manifest',
            from_repo_id=cls.repo_ids[0],
            to_repo_id=cls.repo_ids[1],
        )

    def test_positive_copy_output(self):
        """Assert that the list of manifests in the copy output are correct."""
        units_search = docker_utils.repo_search(
            self.cfg,
            fields='digest',
            repo_id=self.repo_ids[0],
            unit_type='manifest',
        ).stdout
        unit_ids_search = set(re.findall(_DIGEST_RE, units_search))

        # The manifest digests are printed after "docker_manifest:".
        unit_ids_copy = self.copy.stdout.split('docker_manifest:')[1]
        unit_ids_copy = re.findall(r'(?: {2})(\w*:\w*)', unit_ids_copy)
        unit_ids_copy = _truncate_ids(unit_ids_copy)

        self.assertEqual(unit_ids_search, unit_ids_copy)

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

        # Create a pair of repositories.
        docker_utils.repo_create_update(
            cls.cfg,
            enable_v1='false',
            enable_v2='true',
            feed=DOCKER_V2_FEED_URL,
            repo_id=cls.repo_ids[0],
            upstream_name=_UPSTREAM_NAME,
        )
        docker_utils.repo_create_update(cls.cfg, repo_id=cls.repo_ids[1])

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
        units_search = docker_utils.repo_search(
            self.cfg,
            fields='name',
            repo_id=self.repo_ids[0],
            unit_type='tag',
        ).stdout
        unit_ids_search = set(re.findall(_DIGEST_RE, units_search))

        # The tag digests are printed after "docker_tag:".
        unit_ids_copy = self.copy.stdout.split('docker_tag:')[1]
        unit_ids_copy = re.findall(r'(?: {2})(\w*:\w*)', unit_ids_copy)
        unit_ids_copy = _truncate_ids(unit_ids_copy)

        self.assertEqual(unit_ids_search, unit_ids_copy)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        for unit_type in {'manifest', 'tag'}:
            with self.subTest(unit_type=unit_type):
                src_unit_ids, dest_unit_ids = [
                    _get_unit_ids(self.cfg, repo_id, unit_type, _NAME_RE)
                    for repo_id in self.repo_ids
                ]
                self.assertEqual(src_unit_ids, dest_unit_ids)
