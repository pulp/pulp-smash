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

import unittest2

from pulp_smash import api, utils, selectors
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    xml_handler,
    NAMESPACE
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


def get_repo_md(cfg, distributor):
    """Return parsed repomd.xml file."""
    client = api.Client(cfg)
    client.response_handler = xml_handler
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    path = urljoin(path, 'repodata/repomd.xml')
    root_elem = client.get(path)
    return root_elem


def get_timestamps(root_elem):
    """Return dictionary of timestamps for each data entry in repomd."""
    data_elems = root_elem.findall('{%s}data' % NAMESPACE)
    timestamps = {}
    for data in data_elems:
        stamp = data.find('{%s}timestamp' % NAMESPACE).text
        timestamps[data.attrib.get('type')] = stamp
    return timestamps


class NOOPTestCase1(utils.BaseAPITestCase):
    """Test NOOP publish on rpm repo with overrides_config."""

    @classmethod
    def setUpClass(cls):
        """Create one repository with feed, unassociate unit and re-publish.

        Following steps are executed:

        1. Create repository foo with feed, sync and publish it.
        2. assert publish is operational
        3. publish repository again
        4. assert publish is noop
        5. publish with overrides_config
        6. assert publish is operational
        7. publish with overrides_config (identical to step 5)
        8. assert publish is noop

        """
        super(NOOPTestCase1, cls).setUpClass()
        cls.responses = {}
        cls.tasks = {}
        cls.xmldata = {}
        if selectors.bug_is_untestable(1724, cls.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1724')

        # Create and sync a repository.
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(repo_href)  # mark for deletion
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo_href)

        # Add a distributor and publish it.
        distributor = client.post(
            urljoin(repo_href, 'distributors/'),
            gen_distributor(),
        ).json()
        cls.responses['first publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id']},
        ).json()
        cls.xmldata['publish1'] = get_repo_md(cls.cfg, distributor)

        # no op publish
        cls.responses['second publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id']},
        ).json()
        cls.xmldata['publish2'] = get_repo_md(cls.cfg, distributor)

        # publish with overrides, that shouldn't be noop
        cls.responses['third publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id'],
             'config_overrides': {'relative_url': '/foo/bar/repo'}},
        ).json()
        cls.xmldata['publish3'] = get_repo_md(cls.cfg, distributor)

        # publish with overrides, that shouldn't be noop
        cls.responses['fourth publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id'],
             'config_overrides': {'relative_url': '/foo/bar/repo'}},
        ).json()
        cls.xmldata['publish4'] = get_repo_md(cls.cfg, distributor)

        # publish with overrides (identical as in publish3),
        # should be noop
        for publish in ('first publish', 'second publish', 'third publish',
                        'fourth publish'):
            report = cls.responses[publish]
            cls.tasks[publish] = next(api.poll_spawned_tasks(cls.cfg,
                                                             report))

    def test_01_op_publish(self):
        """Test if first publish is operational."""
        self.assertTrue(isinstance(
            self.tasks['first publish']['result']['summary'],
            dict))

    def test_02_noop_publish(self):
        """Test if second publish is noop."""
        self.assertEqual(self.tasks['second publish']['result']['summary'],
                         'Skipped. Nothing changed since last publish')
        timestamps2 = get_timestamps(self.xmldata['publish1'])
        timestamps1 = get_timestamps(self.xmldata['publish2'])
        self.assertEqual(timestamps1, timestamps2)

    def test_03_op_overrides_publish(self):
        """Test if publish with overrides is operational."""
        if selectors.bug_is_untestable(1928, self.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1928')

        self.assertTrue(isinstance(
            self.tasks['first publish']['result']['summary'],
            dict))
        timestamps2 = get_timestamps(self.xmldata['publish2'])
        timestamps3 = get_timestamps(self.xmldata['publish3'])
        self.assertNotEqual(timestamps2, timestamps3)

    def test_04_noop_overrides_publish(self):
        """Test if publish with overrides is operational."""
        if selectors.bug_is_untestable(1928, self.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1928')

        self.assertTrue(isinstance(
            self.tasks['first publish']['result']['summary'],
            dict))
        timestamps3 = get_timestamps(self.xmldata['publish3'])
        timestamps4 = get_timestamps(self.xmldata['publish4'])
        self.assertEqual(timestamps3, timestamps4)


class NOOPTestCase2(utils.BaseAPITestCase):
    """Test NOOP publish on rpm repo with removing units."""

    @classmethod
    def setUpClass(cls):
        """Create one repository with feed, unassociate unit and re-publish.

        Following steps are executed:

        1. Create repository foo with feed, sync and publish it.
        2. assert publish is operational
        3. publish repository again
        4. assert publish is noop
        5. publish with overrides_config
        6. assert publish is operational
        7. publish with overrides_config (identical to step 5)
        8. assert publish is noop

        """
        super(NOOPTestCase2, cls).setUpClass()
        cls.responses = {}
        cls.tasks = {}
        cls.xmldata = {}
        if selectors.bug_is_untestable(1724, cls.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1724')

        # Create and sync a repository.
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(repo_href)  # mark for deletion
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo_href)

        # Add a distributor and publish it.
        distributor = client.post(
            urljoin(repo_href, 'distributors/'),
            gen_distributor(),
        ).json()
        cls.responses['first publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id']},
        ).json()
        cls.xmldata['publish1'] = get_repo_md(cls.cfg, distributor)

        # no op publish
        cls.responses['second publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id']},
        ).json()
        cls.xmldata['publish2'] = get_repo_md(cls.cfg, distributor)

        # Remove unit
        cls.responses['remove unit'] = client.post(
            urljoin(repo_href, 'actions/unassociate/'),
            {'criteria': {'type_ids': ['rpm'], 'limit': 1}}
        )
        # publish after unit removal, that shouldn't be noop
        cls.responses['third publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': distributor['id']}
        ).json()
        cls.xmldata['publish3'] = get_repo_md(cls.cfg, distributor)

        for publish in ('first publish', 'second publish', 'third publish'):
            report = cls.responses[publish]
            cls.tasks[publish] = next(api.poll_spawned_tasks(cls.cfg,
                                                             report))

    def test_01_op_publish(self):
        """Test if first publish is operational."""
        self.assertTrue(isinstance(
            self.tasks['first publish']['result']['summary'],
            dict))

    def test_01_noop_publish(self):
        """Test if second publish is noop."""
        self.assertEqual(self.tasks['second publish']['result']['summary'],
                         'Skipped. Nothing changed since last publish')
        timestamps2 = get_timestamps(self.xmldata['publish1'])
        timestamps1 = get_timestamps(self.xmldata['publish2'])
        self.assertEqual(timestamps1, timestamps2)

    def test_03_op_after_removal(self):
        """Test if publish after unit removal is operational."""
        self.assertTrue(isinstance(
            self.tasks['first publish']['result']['summary'],
            dict))
        timestamps2 = get_timestamps(self.xmldata['publish2'])
        timestamps3 = get_timestamps(self.xmldata['publish3'])
        self.assertNotEqual(timestamps2, timestamps3)
