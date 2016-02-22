# coding=utf-8
"""Tests for copying docker units between repositories."""
from __future__ import unicode_literals
import re

import unittest2
from packaging.version import Version

from pulp_smash import utils
from pulp_smash.tests.docker.cli import utils as docker_utils


class CopyAllImagesTestCase(docker_utils.BaseTestCase,
                            docker_utils.SuccessMixin):
    """Test copying all Images from one repository to another."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v1 registry."""
        super(CopyAllImagesTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        # Create and sync a repository with a v1 feed to bring some Images in.
        docker_utils.create_repo(
            cls.cfg, cls.repo_id, upstream_name='library/busybox',
            sync_v1=True, sync_v2=False)
        docker_utils.sync_repo(cls.cfg, cls.repo_id)

        # Now create a feedless repository and copy the images from the first
        # repository over.
        cls.copy_target = utils.uuid4()
        docker_utils.create_repo(cls.cfg, cls.copy_target)
        cls.completed_proc = docker_utils.copy(cls.cfg, 'image', cls.repo_id,
                                               cls.copy_target)

    @classmethod
    def tearDownClass(cls):
        """Delete the copy_target repo."""
        super(CopyAllImagesTestCase, cls).tearDownClass()
        docker_utils.delete_repo(cls.cfg, cls.copy_target)

    def test_positive_copy_output(self):
        """Assert that the list of image_ids in the copy output are correct."""
        # We need to limit the fields to image_id as a hack to work around
        # https://pulp.plan.io/issues/1696. Doing this has a side effect of
        # showing the image_ids without splitting them with a line break
        # (sigh).
        units_in_src = docker_utils.search(self.cfg, 'image', self.repo_id,
                                           fields=['image_id']).stdout
        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the image_ids. Hello regex my old
        # friend, I've come to talk with you again…
        image_ids_in_src = set(re.findall(r'(?:Image Id:)\s*(.*)',
                                          units_in_src))

        image_ids_printed = set(re.findall(r'(?: {2})(\w*)',
                                           self.completed_proc.stdout))

        self.assertEqual(image_ids_printed, image_ids_in_src)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        units_in_src = docker_utils.search(self.cfg, 'image',
                                           self.repo_id).stdout
        units_in_dest = docker_utils.search(self.cfg, 'image',
                                            self.copy_target).stdout

        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the unit_ids. Hello regex my old
        # friend, I've come to talk with you again…
        units_in_src = set(re.findall(r'(?:Unit Id:)\s*(.*)', units_in_src))
        units_in_dest = set(re.findall(r'(?:Unit Id:)\s*(.*)', units_in_dest))

        self.assertEqual(units_in_src, units_in_dest)

    def test_task_succeeded(self):
        """Assert that "Copied" appears in stdout."""
        self.assertIn('Copied', self.completed_proc.stdout)


class CopyAllManifestsTestCase(docker_utils.BaseTestCase,
                               docker_utils.SuccessMixin):
    """Test copying all Manifests from one repository to another."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry."""
        super(CopyAllManifestsTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        # Create and sync a repository with a v2 feed to bring some Manifests
        # in.
        docker_utils.create_repo(
            cls.cfg, cls.repo_id, upstream_name='library/busybox',
            sync_v1=False, sync_v2=True)
        docker_utils.sync_repo(cls.cfg, cls.repo_id)

        # Now create a feedless repository and copy the manifests from the
        # first repository over.
        cls.copy_target = utils.uuid4()
        docker_utils.create_repo(cls.cfg, cls.copy_target)
        cls.completed_proc = docker_utils.copy(cls.cfg, 'manifest',
                                               cls.repo_id, cls.copy_target)

    @classmethod
    def tearDownClass(cls):
        """Delete the copy_target repo."""
        super(CopyAllManifestsTestCase, cls).tearDownClass()
        docker_utils.delete_repo(cls.cfg, cls.copy_target)

    def test_positive_copy_output(self):
        """Assert that the list of manifests in the copy output are correct."""
        units_in_src = docker_utils.search(self.cfg, 'manifest', self.repo_id,
                                           fields=['digest']).stdout
        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the digests. Hello regex my old
        # friend, I've come to talk with you again…
        manifest_ids_in_src = set(re.findall(r'(?:Digest:)\s*(.*)',
                                             units_in_src))

        # The manifest digests are printed after "docker_manifest:" in the copy
        # output.
        manifest_ids = self.completed_proc.stdout.split('docker_manifest:')[1]
        manifest_ids_printed = re.findall(r'(?: {2})(\w*:\w*)', manifest_ids)
        # Due to https://pulp.plan.io/issues/1696 pulp-admin has split the last
        # character of each of the manifest_ids_in_src items onto the next line
        # which wasn't matched by the regex. That's stupid, but we're going to
        # work around it by chopping the last character off of these as well.
        manifest_ids_printed = set([d[:-1] for d in manifest_ids_printed])

        self.assertEqual(manifest_ids_printed, manifest_ids_in_src)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        units_in_src = docker_utils.search(self.cfg, 'manifest',
                                           self.repo_id).stdout
        units_in_dest = docker_utils.search(self.cfg, 'manifest',
                                            self.copy_target).stdout

        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the unit_ids. Hello regex my old
        # friend, I've come to talk with you again…
        units_in_src = set(re.findall(r'(?:Unit Id:)\s*(.*)', units_in_src))
        units_in_dest = set(re.findall(r'(?:Unit Id:)\s*(.*)', units_in_dest))

        self.assertEqual(units_in_src, units_in_dest)

    def test_task_succeeded(self):
        """Assert that "Copied" appears in stdout."""
        self.assertIn('Copied', self.completed_proc.stdout)


class CopyAllTagsTestCase(docker_utils.BaseTestCase,
                          docker_utils.SuccessMixin):
    """Test copying all Tags from one repository to another."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a docker repository with a v2 registry."""
        super(CopyAllTagsTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.8'):
            raise unittest2.SkipTest('These tests require Pulp 2.8 or above.')
        # Create and sync a repository with a v2 feed to bring some Tags in.
        docker_utils.create_repo(
            cls.cfg, cls.repo_id, upstream_name='library/busybox',
            sync_v1=False, sync_v2=True)
        docker_utils.sync_repo(cls.cfg, cls.repo_id)

        # Now create a feedless repository and copy the tags from the first
        # repository over.
        cls.copy_target = utils.uuid4()
        docker_utils.create_repo(cls.cfg, cls.copy_target)
        cls.completed_proc = docker_utils.copy(cls.cfg, 'tag', cls.repo_id,
                                               cls.copy_target)

    @classmethod
    def tearDownClass(cls):
        """Delete the copy_target repo."""
        super(CopyAllTagsTestCase, cls).tearDownClass()
        docker_utils.delete_repo(cls.cfg, cls.copy_target)

    def test_positive_copy_output(self):
        """Assert that the list of tags in the copy output are correct."""
        units_in_src = docker_utils.search(self.cfg, 'tag', self.repo_id,
                                           fields=['name']).stdout
        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the digests. Hello regex my old
        # friend, I've come to talk with you again…
        tag_ids_in_src = set(re.findall(r'(?:Digest:)\s*(.*)', units_in_src))

        # The tag digests are printed after "docker_tag:" in the copy output.
        tag_ids = self.completed_proc.stdout.split('docker_tag:')[1]
        tag_ids_printed = re.findall(r'(?: {2})(\w*:\w*)', tag_ids)
        # Due to https://pulp.plan.io/issues/1696 pulp-admin has split the last
        # character of each of the tag_ids_in_src items onto the next line
        # which wasn't matched by the regex. That's stupid, but we're going to
        # work around it by chopping the last character off of these as well.
        tag_ids_printed = set([d[:-1] for d in tag_ids_printed])

        self.assertEqual(tag_ids_printed, tag_ids_in_src)

    def test_positive_units_copied(self):
        """Assert that all units were copied."""
        tags_in_src = docker_utils.search(self.cfg, 'tag', self.repo_id).stdout
        tags_in_dest = docker_utils.search(self.cfg, 'tag',
                                           self.copy_target).stdout
        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the names. Hello regex my old
        # friend, I've come to talk with you again…
        tags_in_src = set(re.findall(r'(?:Name:)\s*(.*)', tags_in_src))
        tags_in_dest = set(re.findall(r'(?:Name:)\s*(.*)', tags_in_dest))

        # The Manifests should have been pulled over as well since they are
        # recursively copied.
        manifests_in_src = docker_utils.search(self.cfg, 'manifest',
                                               self.repo_id).stdout
        manifests_in_dest = docker_utils.search(self.cfg, 'manifest',
                                                self.copy_target).stdout
        # Due to https://pulp.plan.io/issues/1693 it is not possible to get
        # pulp-admin to limit the output to the unit_ids. Hello regex my old
        # friend, I've come to talk with you again…
        manifests_in_src = set(re.findall(r'(?:Name:)\s*(.*)',
                                          manifests_in_src))
        manifests_in_dest = set(re.findall(r'(?:Name:)\s*(.*)',
                                           manifests_in_dest))

        self.assertEqual(tags_in_src, tags_in_dest)
        self.assertEqual(manifests_in_src, manifests_in_dest)

    def test_task_succeeded(self):
        """Assert that "Copied" appears in stdout."""
        self.assertIn('Copied', self.completed_proc.stdout)
