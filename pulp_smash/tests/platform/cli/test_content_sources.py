# coding=utf-8
"""Tests for list/refresh/delete content sources."""
from __future__ import unicode_literals

import unittest2
from packaging.version import Version

from pulp_smash import cli, config
from pulp_smash.constants import CONTENT_SOURCE_ID


def _get_content_source_ids(server_config):
    """Get the id list of all content sources, or empty list.

    :param server_config: Information about the Pulp server being targeted.
    :type server_config: pulp_smash.config.ServerConfig server_config.
    :returns: A list of content source IDs, where each ID is a string.
    """
    keyword = 'Source Id:'
    completed_proc = cli.Client(server_config).run(
        'pulp-admin content sources list'.split()
    )
    lines = [
        line for line in completed_proc.stdout.splitlines()
        if keyword in line
    ]
    return [line.split(keyword)[1].strip() for line in lines]


class RefreshAndDeleteContentSourcesTestCase(unittest2.TestCase):
    """Test whether pulp-admin client can refresh and delete content source.

    This test case targets Pulp #1692`_ and `Pulp Smash #141`_. The
    `content sources`_ documentation describes the CLI syntax. The
    test steps are as follows:

    1. Create configuration file of a content source.
    2. Check whether the content sources list is empty.
    3. Refresh all content sources. Verify no errors are reported.
    4. Refresh a specified content source. Verify no errors are reported.
    5. Remove the specified content source. Verify that the source is
        actually deleted.

    For now, a content source is manually added into the directory:
    `/etc/pulp/content/sources/conf.d/`, and the test are written with
    the assumption that the content source file is present.

    .. _Pulp #1692:  https://pulp.plan.io/issues/1692
    .. _Pulp Smash #141: https://github.com/PulpQE/pulp-smash/issues/141
    .. _content sources:
        http://pulp.readthedocs.io/en/latest/user-guide/content-sources.html
    """

    @classmethod
    def setUpClass(cls):
        """Verify if content resources exist."""
        cls.cfg = config.get_config()
        cls.client = cli.Client(cls.cfg)
        cls.source_id = CONTENT_SOURCE_ID
        if cls.cfg.version < Version('2.8.3'):
            raise unittest2.SkipTest('This test requires at least 2.8.3')

    def test_01_refresh_all_sources(self):
        """Refresh all content sources."""
        completed_proc = self.client.run(
            'pulp-admin content sources refresh'.split()
        )
        self.check_error_existing(completed_proc)

    def test_02_refresh_specific_source(self):
        """Refresh a specific content sources."""
        if len(_get_content_source_ids(self.cfg)) == 0:
            raise unittest2.SkipTest(
                'This test requires a content source defined in: '
                '`/etc/pulp/content/sources/conf.d`'
            )
        completed_proc = self.client.run((
            'pulp-admin content sources refresh '
            '--source-id {}'.format(self.source_id)
        ).split())
        self.check_error_existing(completed_proc)

    def test_03_delete_content_sources(self):
        """Delete a specific content source."""
        self.client.run((
            'pulp-admin content catalog delete -s {}'.format(self.source_id)
        ).split())
        # Verify that the specified content source does not exist.
        self.assertNotIn(self.source_id, _get_content_source_ids(self.cfg))

    def check_error_existing(self, completed_proc):
        """Verify no errors were reported."""
        phrase = 'Task Failed'
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn(phrase, getattr(completed_proc, stream))
