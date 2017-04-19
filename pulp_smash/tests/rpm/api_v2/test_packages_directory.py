# coding=utf-8
"""Test re-publish repository after unassociating content.

Following steps are executed in order to test correct functionality of
repository created with valid feed.

1. Create repository foo with valid feed, run sync, add distributor to it and
   publish over http and https.
2. Pick a unit X and and assert it is accessible.
3. Remove unit X from repository foo and re-publish.
4. Assert unit X is not accessible.
"""
from __future__ import unicode_literals

import os

from pulp_smash import api, utils, selectors
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import (
    NAMESPACE,
    gen_distributor,
    gen_repo,
    xml_handler,
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


def get_repo_md(cfg, distributor_rel_url):
    """Return parsed repomd.xml file."""
    path = urljoin('/pulp/repos/', distributor_rel_url)
    path = urljoin(path, 'repodata/repomd.xml')
    return api.Client(cfg, xml_handler).get(path)


def get_repo_primary(cfg, distributor_rel_url, relative_location):
    """Return parsed primary.xml file."""
    path = urljoin('/pulp/repos/', distributor_rel_url)
    path = urljoin(path, relative_location)
    return api.Client(cfg, xml_handler).get(path)


def gen_rpm_repo(client):
    """Create rpm repo with importer and associate it with yum_distributor."""
    body = gen_repo()
    body['importer_config']['feed'] = RPM_FEED_URL
    repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
    distributor = client.post(
        urljoin(repo_href, 'distributors/'),
        gen_distributor(),
    ).json()
    return repo_href, distributor


def get_locations(xml_elem):
    """Get 'location' elements for xml string."""
    xpath = '{{{}}}data'.format(NAMESPACE)
    data_elements = xml_elem.findall(xpath)
    xpath = '{{{}}}location'.format(NAMESPACE)
    locations = [element.find(xpath) for element in data_elements]
    ret = [location.get('href') for location in locations]
    return ret


class PackagesDirectoryTestCase(utils.BaseAPITestCase):
    """Test packages_directory feature."""

    @classmethod
    def setUpClass(cls):
        """Create one repository with feed, publish, test packages location.

        Following steps are executed:

        1. Create repository foo with feed, sync and publish it.
        2. Check packages locations in repodata
        3. Republish with 'packages_directory' in  config_override
        4. Check packages locations in repodata
        """
        super(PackagesDirectoryTestCase, cls).setUpClass()
        cls.responses = {}
        cls.xmldata = {}

        # Create and sync a repository.
        client = api.Client(cls.cfg)

        repo_href, distributor = gen_rpm_repo(client)
        cls.resources.add(repo_href)
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo_href)

        repo_href2, distributor2 = gen_rpm_repo(client)
        cls.resources.add(repo_href2)
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo_href2)

        # first publish - default packages directory
        cls.responses['first publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id']},
        )
        repomd_xml = get_repo_md(
            cls.cfg,
            distributor['config']['relative_url'],
        )
        types_locations = get_locations(repomd_xml)
        location = None
        for location in types_locations:
            if 'primary.xml.gz' in location:
                break
        cls.responses['publish1_xml'] = get_repo_primary(
            cls.cfg,
            distributor['config']['relative_url'],
            location
        )

        # second publish - custom packages directory
        cls.responses['second publish'] = client.post(
            urljoin(repo_href2, 'actions/publish/'),
            {'id': distributor2['id'],
             'config_overrides': {'packages_directory': 'Packages'}},
        )

        if selectors.bug_is_untestable(1976, cls.cfg.version):
            return

        repomd_xml = get_repo_md(
            cls.cfg,
            distributor2['config']['relative_url'],
        )
        types_locations = get_locations(repomd_xml)
        for location in types_locations:
            if 'primary.xml.gz' in location:
                break
        cls.responses['publish2_xml'] = get_repo_primary(
            cls.cfg,
            distributor2['config']['relative_url'],
            location
        )

    def test_default_packages_directory(self):
        """Verify the packages are places with same directory as repodata."""
        packages_locations = get_locations(self.responses['publish1_xml'])
        for location in packages_locations:
            self.assertEqual(os.path.dirname(location), '')

    def test_custom_packages_directory(self):
        """Verify the packages are places with 'Packages' directory."""
        if selectors.bug_is_untestable(1976, self.cfg.version):
            return
        packages_locations = get_locations(self.responses['publish2_xml'])
        for location in packages_locations:
            self.assertEqual(os.path.dirname(location), 'Packages')
