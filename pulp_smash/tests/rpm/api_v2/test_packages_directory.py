# coding=utf-8
"""Tests for the ``packages_directory`` distributor option.

One can configure a distributor with a ``packages_directory`` configuration
option. This option controls whether RPMs are published in the same directory
as the ``repodata`` directory, or somewhere else. This module tests this
feature. For more information, see `Pulp issue #1976`_.

.. _Pulp issue #1976: https://pulp.plan.io/issues/1976
"""
import os
import unittest
from urllib.parse import urljoin

from pulp_smash import api, selectors, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL, RPM_NAMESPACES
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    xml_handler,
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def get_parse_repodata_xml(server_config, distributor, file_path):
    """Fetch, parse and return an XML file from a ``repodata`` directory.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param distributor: Information about a distributor. It should be a dict
        containing at least ``{'config': {'relative_url': …}}``.
    :param file_path: The path to an XML file, relative to the distributor's
        relative URL. For example: ``repodata/repomd.xml``.
    :returns: The XML document, parsed as an ``xml.etree.ElementTree`` object.
    """
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    path = urljoin(path, file_path)
    return api.Client(server_config, xml_handler).get(path)


def get_parse_repodata_primary_xml(cfg, distributor):
    """Fetch, decompress, parse and return a ``repodata/…primary.xml.gz`` file.

    :param pulp_smash.config.ServerConfig cfg: Information about the Pulp
        server being targeted.
    :param distributor: Information about a distributor. It should be a dict
        containing at least ``{'config': {'relative_url': …}}``.
    :returns: An ``xml.etree.ElementTree`` object.
    """
    repomd_xml = get_parse_repodata_xml(
        cfg,
        distributor,
        'repodata/repomd.xml'
    )
    primary_xml_hrefs = [
        href for href in get_file_hrefs(repomd_xml)
        if href.endswith('primary.xml.gz')
    ]
    assert len(primary_xml_hrefs) == 1
    return get_parse_repodata_xml(cfg, distributor, primary_xml_hrefs[0])


def get_package_hrefs(primary_xml):
    """Return the href of each package in a ``primary.xml`` file.

    :param primary_xml: An ``xml.etree.ElementTree`` object representing the
        root of a ``primary.xml`` document.
    :returns: An iterable of hrefs, with each href as a string.
    """
    package_xpath = '{{{}}}package'.format(RPM_NAMESPACES['metadata/common'])
    location_xpath = '{{{}}}location'.format(RPM_NAMESPACES['metadata/common'])
    packages = primary_xml.findall(package_xpath)
    locations = [package.find(location_xpath) for package in packages]
    return tuple((location.get('href') for location in locations))


def get_file_hrefs(repomd_xml):
    """Return the href of each file in a ``repomd.xml`` file.

    :param repomd_xml: An ``xml.etree.ElementTree`` object representing the
        root of a ``repomd.xml`` document.
    :returns: An iterable of hrefs, with each href as a string.
    """
    data_xpath = '{{{}}}data'.format(RPM_NAMESPACES['metadata/repo'])
    location_xpath = '{{{}}}location'.format(RPM_NAMESPACES['metadata/repo'])
    data = repomd_xml.findall(data_xpath)
    locations = [datum.find(location_xpath) for datum in data]
    return tuple((location.get('href') for location in locations))


class PackagesDirectoryTestCase(utils.BaseAPITestCase):
    """Test the distributor ``packages_directory`` option."""

    @classmethod
    def setUpClass(cls):
        """Create a repository with a feed and sync it."""
        super(PackagesDirectoryTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(2277, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        cls.repo_href = client.post(REPOSITORY_PATH, body)['_href']
        cls.resources.add(cls.repo_href)
        utils.sync_repo(cls.cfg, cls.repo_href)

    def test_default_behaviour(self):
        """Do not use the ``packages_directory`` option.

        Create a distributor with default options, and use it to publish the
        repository. Verify packages end up in the current directory, relative
        to the published repository's root. (This same directory contains the
        ``repodata`` directory, and it may be changed by setting the
        distributor's ``relative_url``.)
        """
        client = api.Client(self.cfg, api.json_handler)
        distributor = client.post(
            urljoin(self.repo_href, 'distributors/'),
            gen_distributor(),
        )
        client.post(urljoin(self.repo_href, 'actions/publish/'), {
            'id': distributor['id']
        })
        primary_xml = get_parse_repodata_primary_xml(self.cfg, distributor)
        package_hrefs = get_package_hrefs(primary_xml)
        self.assertGreater(len(package_hrefs), 0)
        for package_href in package_hrefs:
            with self.subTest(package_href=package_href):
                self.assertEqual(os.path.dirname(package_href), '')

    def test_distributor_config(self):
        """Use the ``packages_directory`` distributor option.

        Create a distributor with the ``packages_directory`` option set, and
        use it to publish the repository. Verify packages end up in the
        specified directory, relative to the published repository's root.
        """
        if selectors.bug_is_untestable(1976, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1976')
        client = api.Client(self.cfg, api.json_handler)
        body = gen_distributor()
        packages_dir = utils.uuid4()
        body['distributor_config']['packages_directory'] = packages_dir
        distributor = client.post(
            urljoin(self.repo_href, 'distributors/'),
            body
        )
        client.post(urljoin(self.repo_href, 'actions/publish/'), {
            'id': distributor['id'],
        })
        primary_xml = get_parse_repodata_primary_xml(self.cfg, distributor)
        package_hrefs = get_package_hrefs(primary_xml)
        self.assertGreater(len(package_hrefs), 0)
        for package_href in package_hrefs:
            with self.subTest(package_href=package_href):
                self.assertEqual(os.path.dirname(package_href), packages_dir)

    def test_publish_override_config(self):
        """Use the ``packages_directory`` publish override option.

        Create a distributor with default options, and use it to publish the
        repository. Specify the ``packages_directory`` option during the
        publish as an override option. Verify packages end up in the specified
        directory, relative to the published repository's root.
        """
        if selectors.bug_is_untestable(1976, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1976')
        client = api.Client(self.cfg, api.json_handler)
        distributor = client.post(
            urljoin(self.repo_href, 'distributors/'),
            gen_distributor(),
        )
        packages_dir = utils.uuid4()
        client.post(urljoin(self.repo_href, 'actions/publish/'), {
            'id': distributor['id'],
            'override_config': {'packages_directory': packages_dir},
        })
        primary_xml = get_parse_repodata_primary_xml(self.cfg, distributor)
        package_hrefs = get_package_hrefs(primary_xml)
        self.assertGreater(len(package_hrefs), 0)
        for package_href in package_hrefs:
            with self.subTest(package_href=package_href):
                self.assertEqual(os.path.dirname(package_href), packages_dir)
