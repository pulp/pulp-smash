# coding=utf-8
"""Tests for Pulp's `content sources`_ feature.

.. _content sources:
    http://docs.pulpproject.org/user-guide/content-sources.html
"""
import os
import unittest
from io import StringIO
from urllib.parse import urlsplit, urlunsplit

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp2.constants import CONTENT_SOURCES_PATH
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import

_HEADERS = {'X-RHUI-ID', 'X-CSRF-TOKEN'}


class ValidHeadersTestCase(unittest.TestCase):
    """Define a content source with valid headers.

    See:

    * `Pulp #1282 <https://pulp.plan.io/issues/1282>`_
    * `Pulp Smash #643 <https://github.com/PulpQE/pulp-smash/issues/643>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create a content source with valid headers."""
        cls.cfg = config.get_config()
        if selectors.bug_is_untestable(1282, cls.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1282')
        cls.cs_kwargs = {
            'source_id': utils.uuid4(),
            'headers': ' '.join(
                '{}={}'.format(header, utils.uuid4()) for header in _HEADERS
            ),
        }
        cs_body = _gen_content_source_body(**cls.cs_kwargs)
        cls.cs_path = _gen_content_source(cls.cfg, cs_body)

    def test_list_content_sources(self):
        """List Pulp's content sources.

        Assert that:

        1. The list includes an entry corresponding to the newly defined
           content source configuration file.
        2. This list entry includes the headers defined in the configuration
           file.
        """
        client = api.Client(self.cfg, api.json_handler)
        sources = client.get('/pulp/api/v2/content/sources/')
        source_id = self.cs_kwargs['source_id']
        sources_by_id = {source['source_id']: source for source in sources}
        self.assertIn(source_id, sources_by_id)

        source_headers = self.cs_kwargs['headers']
        self.assertEqual(source_headers, sources_by_id[source_id]['headers'])

    def test_refresh_content_sources(self):
        """Refresh Pulp's content sources.

        Assert that the refresh completes successfully.
        """
        client = api.Client(self.cfg)
        client.post('/pulp/api/v2/content/sources/action/refresh/')

    @classmethod
    def tearDownClass(cls):
        """Destroy the created content source."""
        sudo = () if utils.is_root(cls.cfg) else ('sudo',)
        cli.Client(cls.cfg).run(sudo + ('rm', '-f', cls.cs_path))


class InvalidHeadersTestCase(unittest.TestCase):
    """Define a content source with invalid headers.

    See:

    * `Pulp #1282 <https://pulp.plan.io/issues/1282>`_
    * `Pulp Smash #643 <https://github.com/PulpQE/pulp-smash/issues/643>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create a content source with invalid headers."""
        cls.cfg = config.get_config()
        if selectors.bug_is_untestable(1282, cls.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1282')
        cls.cs_kwargs = {
            'source_id': utils.uuid4(),
            'headers': ' '.join(header + utils.uuid4() for header in _HEADERS),
        }
        cs_body = _gen_content_source_body(**cls.cs_kwargs)
        cls.cs_path = _gen_content_source(cls.cfg, cs_body)

    def test_content_sources(self):
        """List Pulp's content sources.

        Assert that the list doesn't include an entry corresponding to the
        newly defined content source configuration file.
        """
        client = api.Client(self.cfg, api.json_handler)
        sources = client.get('/pulp/api/v2/content/sources/')
        source_id = self.cs_kwargs['source_id']
        sources_by_id = {source['source_id']: source for source in sources}
        self.assertNotIn(source_id, sources_by_id)

    def test_refresh_content_sources(self):
        """Refresh Pulp's content sources.

        Assert that the refresh completes successfully. It should complete
        successfully because the broken content source is completely skipped.
        """
        client = api.Client(self.cfg)
        client.post('/pulp/api/v2/content/sources/action/refresh/')

    @classmethod
    def tearDownClass(cls):
        """Destroy the created content source."""
        sudo = () if utils.is_root(cls.cfg) else ('sudo',)
        cli.Client(cls.cfg).run(sudo + ('rm', '-f', cls.cs_path))


def _gen_content_source(cfg, content_source_body):
    """Write out a content source to a system and return its path.

    :param content_source_body: A string that can be used as the body of a
        content source file. Consider using :func:`_gen_content_source_body`.
    :return: The path to the content source file.
    """
    sudo = '' if utils.is_root(cfg) else 'sudo'
    path = os.path.join(CONTENT_SOURCES_PATH, utils.uuid4() + '.conf')
    client = cli.Client(cfg)
    client.machine.session().run(
        "{} bash -c \"echo >'{}' '{}'\""
        .format(sudo, path, content_source_body)
    )
    return path


def _gen_content_source_body(**kwargs):
    """Generate a string that can be used as the body of a content source file.

    :param kwargs: Key-value pairs to insert into the content source file. If a
        required kwarg is not passed in, a default value is generated. The key
        "source_id" is treated specially. It is used in the section header at
        the top of a content source file.
    :return: A string that can be used as the body of a content sources file.
    """
    kwargs = kwargs.copy()  # shadow this parameter
    source_id = kwargs.pop('source_id', utils.uuid4())
    if 'base_url' not in kwargs:
        kwargs['base_url'] = urlunsplit(
            ('https',) + urlsplit(PULP_FIXTURES_BASE_URL)[1:]
        )
    if 'enabled' not in kwargs:
        kwargs['enabled'] = '1'
    if 'name' not in kwargs:
        kwargs['name'] = utils.uuid4()
    if 'paths' not in kwargs:
        kwargs['paths'] = 'rpm-unsigned/'
    if 'type' not in kwargs:
        kwargs['type'] = 'yum'
    with StringIO() as body:
        body.write('[{}]\n'.format(source_id))
        for key, val in kwargs.items():
            body.write('{}: {}\n'.format(key, val))
        return body.getvalue()
