# coding=utf-8
"""Tests for the published repository layout.

Starting with Pulp 2.12, YUM distributor must publish repositories using the
layout where the packages are published to into ``Packages/<first_letter>``
where ``<first_letter>`` is the first letter of a given RPM package. For
example, the ``bear.rpm`` package will be published into
``Packages/b/bear.rpm``. For more information, see `Pulp issue #1976`_.

Old versions of Pulp uses the old layout where all repository's packages were
published on the root of the repository directory not inside the
``Packages/<first_letter>`` subdirectory.

.. _Pulp issue #1976: https://pulp.plan.io/issues/1976
"""
import os
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM_NAMESPACES,
    RPM_SIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    xml_handler,
)
from pulp_smash.tests.rpm.utils import check_issue_2277
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def get_parse_repodata_xml(server_config, distributor, file_path):
    """Fetch, parse and return an XML file from a ``repodata`` directory.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp deployment being targeted.
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

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        deployment being targeted.
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


class RepositoryLayoutTestCase(utils.BaseAPITestCase):
    """Test the YUM distributor publishing repository layout."""

    def test_all(self):
        """Do not use the ``packages_directory`` option.

        Create a distributor with default options, and use it to publish the
        repository. Verify packages end up in the current directory, relative
        to the published repository's root. (This same directory contains the
        ``repodata`` directory, and it may be changed by setting the
        distributor's ``relative_url``.)
        """
        if check_issue_2277(self.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(self.cfg, repo)
        distributor = client.post(
            urljoin(repo['_href'], 'distributors/'),
            gen_distributor(),
        )
        utils.publish_repo(self.cfg, repo, {'id': distributor['id']})
        primary_xml = get_parse_repodata_primary_xml(self.cfg, distributor)
        package_hrefs = get_package_hrefs(primary_xml)
        self.assertGreater(len(package_hrefs), 0)
        for package_href in package_hrefs:
            with self.subTest(package_href=package_href):
                dirname = os.path.dirname(package_href)
                if self.cfg.version < Version('2.12'):
                    self.assertEqual(dirname, '')
                else:
                    # e.g. 'Packages/a'[:-1] == 'Packages/'
                    self.assertEqual(dirname[:-1], 'Packages/')
