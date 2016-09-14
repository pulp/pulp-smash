# coding=utf-8
"""Tests for list/refresh/delete content sources."""
import os
import unittest
from io import StringIO

from packaging.version import Version
from pulp_smash import cli, config
from pulp_smash.constants import CONTENT_SOURCES_PATH, RPM_FEED_URL
from pulp_smash.utils import is_root, pulp_admin_login, uuid4


def generate_content_source(server_config, name, **kwargs):
    """Generate a content source file and returns its remote path.

    See `Defining a Content Source`_ for more information.

    .. _Defining a Content Source:
        http://docs.pulpproject.org/user-guide/content-sources.html#defining-a-content-source

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param name: file name and content source id (string inside []).
    :param kwargs: each item will be converted to content source properties
        where the key is the property name and the value its value.
    :returns: the remote path of the created content source file.
    """
    content_source = StringIO()
    content_source.write('[{}]\n'.format(name))
    path = os.path.join(
        '{}'.format(CONTENT_SOURCES_PATH), '{}.conf'.format(name))
    if 'name' not in kwargs:
        content_source.write('{}: {}\n'.format('name', name))
    for key, value in kwargs.items():
        content_source.write('{}: {}\n'.format(key, value))
    client = cli.Client(server_config)
    sudo = '' if is_root(server_config) else 'sudo '
    client.machine.session().run(
        'echo "{}" | {}tee {} > /dev/null'.format(
            content_source.getvalue(),
            sudo,
            path
        )
    )
    content_source.close()
    return path


def _get_content_source_ids(server_config):
    """Get the id list of all content sources, or empty list.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
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


class RefreshAndDeleteContentSourcesTestCase(unittest.TestCase):
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

    .. _Pulp #1692:  https://pulp.plan.io/issues/1692
    .. _Pulp Smash #141: https://github.com/PulpQE/pulp-smash/issues/141
    .. _content sources:
        http://pulp.readthedocs.io/en/latest/user-guide/content-sources.html
    """

    @classmethod
    def setUpClass(cls):
        """Create a content source."""
        super(RefreshAndDeleteContentSourcesTestCase, cls).setUpClass()
        cls.cfg = config.get_config()
        if cls.cfg.version < Version('2.8.6'):
            raise unittest.SkipTest('This test requires at least 2.8.6')
        pulp_admin_login(cls.cfg)
        cls.client = cli.Client(cls.cfg)
        cls.content_source_id = uuid4()
        content_source_path = generate_content_source(
            cls.cfg,
            cls.content_source_id,
            enabled='1',
            type='yum',
            base_url=RPM_FEED_URL,
        )
        sudo = '' if is_root(cls.cfg) else 'sudo '
        cls.responses = [
            cls.client.run(
                'pulp-admin content sources refresh'.split()
            ),
            _get_content_source_ids(cls.cfg),
            cls.client.run(
                'pulp-admin content sources refresh --source-id {}'
                .format(cls.content_source_id).split()
            ),
        ]
        cls.client.run(
            '{}rm -f {}'.format(sudo, content_source_path).split())
        cls.responses.append(_get_content_source_ids(cls.cfg))

    def test_refresh_all_sources(self):
        """Refresh all content sources."""
        self._assert_not_task_failed(self.responses[0])

    def test_list_content_sources(self):
        """Check if content sources can be listed."""
        self.assertIn(self.content_source_id, self.responses[1])

    def test_refresh_content_source(self):
        """Refresh a specific content source."""
        self._assert_not_task_failed(self.responses[2])

    def test_delete_content_sources(self):
        """Check if a content source can be deleted."""
        self.assertNotIn(self.content_source_id, self.responses[3])

    def _assert_not_task_failed(self, response):
        """Ensure there is no task failed."""
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn('Task Failed', getattr(response, stream))
