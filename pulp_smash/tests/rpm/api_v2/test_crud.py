# coding=utf-8
"""Tests that CRUD RPM repositories.

For information on repository CRUD operations, see `Creation, Deletion and
Configuration
<http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html>`_.
"""
import os
import unittest
from urllib.parse import urljoin

import requests
from packaging import version

from pulp_smash import api, cli, selectors, utils
from pulp_smash.constants import (
    REPOSITORY_GROUP_PATH,
    REPOSITORY_PATH,
    RPM_UNSIGNED_FEED_URL,
    RPM_WITH_PULP_DISTRIBUTION_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    gen_repo_group
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CrudTestCase(utils.BaseAPICrudTestCase):
    """CRUD a minimal RPM repository."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        return gen_repo()

    @staticmethod
    def update_body():
        """Return a dict for updating a repository."""
        return {'delta': {'display_name': utils.uuid4()}}


class CrudWithFeedTestCase(CrudTestCase):
    """CRUD an RPM repository with a feed URL."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        body = CrudTestCase.create_body()
        body['importer_config'] = {'feed': utils.uuid4()}
        return body


class FeedURLUnquoteTestCase(utils.BaseAPITestCase):
    """Check that feed URLs are unquoted.

    See https://pulp.plan.io/issues/2520.
    """

    def test_all(self):
        """Ensure Pulp unquote feed URLs."""
        if self.cfg.version < version.Version('2.11'):
            self.skipTest('Feed URL unquoting is available on Pulp 2.11+')
        client = api.Client(self.cfg, api.json_handler)
        body = CrudTestCase.create_body()
        body['importer_config'] = {
            'feed': 'http://usern%40me:password@example.com/repo',
        }
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        importer_config = repo['importers'][0]['config']
        self.assertEqual(importer_config['basic_auth_username'], 'usern@me')
        self.assertEqual(importer_config['feed'], 'http://example.com/repo')


class PulpDistributionTestCase(utils.BaseAPITestCase):
    """Check if a feed with PULP_DISTRIBUTION.xml syncs properly.

    See https://pulp.plan.io/issues/1086
    """

    def test_all(self):
        """Check for content synced from a feed with PULP_DISTRIBUTION.xml."""
        if self.cfg.version < version.Version('2.11.2'):
            self.skipTest(
                'PULP_DISTRIBUTION.xml improved parsing is available on Pulp '
                '2.11.2+'
            )
        client = api.Client(self.cfg, api.json_handler)
        distributor = gen_distributor()
        distributor['auto_publish'] = True
        body = gen_repo()
        body['distributors'] = [distributor]
        body['importer_config'] = {
            'feed': RPM_WITH_PULP_DISTRIBUTION_FEED_URL,
        }
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(self.cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        self.assertEqual(repo['content_unit_counts']['distribution'], 1)
        cli_client = cli.Client(self.cfg, cli.code_handler)
        relative_url = repo['distributors'][0]['config']['relative_url']
        sudo = () if utils.is_root(self.cfg) else ('sudo',)
        pulp_distribution = cli_client.run(sudo + (
            'cat',
            os.path.join(
                '/var/lib/pulp/published/yum/http/repos/',
                relative_url,
                'PULP_DISTRIBUTION.xml',
            ),
        )).stdout
        # make sure published repository PULP_DISTRIBUTION.xml does not include
        # any extra file from the original repo's PULP_DISTRIBUTION.xml under
        # metadata directory
        self.assertNotIn('metadata/productid', pulp_distribution)

        release_info = cli_client.run(sudo + (
            'cat',
            os.path.join(
                '/var/lib/pulp/published/yum/http/repos/',
                relative_url,
                'release-notes/release-info',
            ),
        )).stdout
        response = requests.get(urljoin(
            urljoin(RPM_WITH_PULP_DISTRIBUTION_FEED_URL, 'release-notes/'),
            'release-info',
        ))
        # make sure published repository has extra files outside the metadata
        # directory from the origiginal repo's PULP_DISTRIBUTION.xml
        self.assertEqual(release_info, response.text)


class RepositoryGroupCrudTestCase(utils.BaseAPITestCase):
    """CRUD a minimal RPM repositories' groups.

    For information on repositories' groups CRUD operations, see `Creation,
    Delete, and Update
    <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/groups/cud.html>`
    """

    @classmethod
    def setUpClass(cls):
        """Create, update, read and delete a repository group."""
        super(RepositoryGroupCrudTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.bodies = {
            'create': gen_repo_group(),
            'update': {'display_name': utils.uuid4()},
        }
        cls.responses = {}
        cls.responses['create'] = client.post(
            REPOSITORY_GROUP_PATH,
            cls.bodies['create'],
        )
        repo_href = cls.responses['create'].json()['_href']
        cls.responses['update'] = client.put(repo_href, cls.bodies['update'])
        cls.responses['read'] = client.get(repo_href, params={'details': True})
        cls.responses['delete'] = client.delete(repo_href)

    def test_status_codes(self):
        """Assert each response has a correct status code."""
        for response, code in (
                ('create', 201),
                ('update', 200),
                ('read', 200),
                ('delete', 200)):
            with self.subTest((response, code)):
                self.assertEqual(self.responses[response].status_code, code)

    def test_create(self):
        """Assert the created repository group has all requested attributes.

        Walk through each of the attributes present on the create body and
        verify the attribute is present in the repository group.
        """
        received = self.responses['create'].json()
        for key, value in self.bodies['create'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_update(self):
        """Assert the repo group update response has the requested changes."""
        received = self.responses['update'].json()
        for key, value in self.bodies['update'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_read(self):
        """Assert the repo group update response has the requested changes."""
        received = self.responses['read'].json()
        for key, value in self.bodies['update'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)


class RPMDistributorTestCase(utils.BaseAPITestCase):
    """RPM distributor tests."""

    def test_update_checksum_type(self):
        """Check if RPM distributor can receive null checksum_type.

        See: https://pulp.plan.io/issues/2134.
        """
        if self.cfg.version < version.Version('2.9'):
            raise unittest.SkipTest('This test requires Pulp 2.9 or above.')
        client = api.Client(self.cfg, api.json_handler)
        distributor = gen_distributor()
        body = gen_repo()
        body['distributors'] = [distributor]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        for checksum_type in (None, 'sha256', None):
            client.put(repo['_href'], {
                'distributor_configs': {
                    distributor['distributor_id']: {
                        'checksum_type': checksum_type,
                    }
                }
            })
            repo = client.get(repo['_href'], params={'details': True})
            config = repo['distributors'][0]['config']
            self.assertEqual(config.get('checksum_type'), checksum_type)


class LastUnitAddedTestCase(utils.BaseAPITestCase):
    """Tests for ensuring proper last_unit_added behavior."""

    def setUp(self):
        """Perform common set-up tasks."""
        self.client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'] = {'feed': RPM_UNSIGNED_FEED_URL}
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        self.repo = self.client.get(repo['_href'], params={'details': True})

    def test_update_on_sync(self):
        """Check if syncing a repo updates ``last_unit_added``.

        Do the following:

        1. Create a repository with a feed.
        2. Assert the repository's ``last_unit_added`` attribute is null.
        3. Sync the repository.
        4. Assert the repository's ``last_unit_added`` attribute is non-null.
        """
        self.assertIsNone(self.repo['last_unit_added'])
        utils.sync_repo(self.cfg, self.repo)
        self.repo = self.client.get(
            self.repo['_href'], params={'details': True})
        self.assertIsNotNone(self.repo['last_unit_added'])

    def test_update_on_copy(self):
        """Check if copying units into a repo updates ``last_unit_added``.

        Do the following:

        1. Create a repository with a feed and sync it.
        2. Create a second repository. Assert the second repository's
           ``last_unit_added`` attribute is null.
        3. Copy a content unit from first repository to the second. Assert the
           second repository's ``last_unit_added`` attribute is non-null.
        4. Publish the second repository. Assert its ``last_unit_added``
           attribute is non-null.
        """
        if selectors.bug_is_untestable(2688, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2688')

        # create a repo with a feed and sync it
        utils.sync_repo(self.cfg, self.repo)
        self.repo = self.client.get(
            self.repo['_href'], params={'details': True})

        # create a second repository
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo2 = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo2['_href'])
        repo2 = self.client.get(repo2['_href'], params={'details': True})
        with self.subTest(comment='after repository creation'):
            self.assertIsNone(repo2['last_unit_added'])

        # copy a content unit from the first repo to the second
        self.client.post(urljoin(repo2['_href'], 'actions/associate/'), {
            'source_repo_id': self.repo['id'],
            'criteria': {
                'filters': {'unit': {'name': 'bear'}},
                'type_ids': ['rpm'],
            },
        })
        repo2 = self.client.get(repo2['_href'], params={'details': True})
        with self.subTest(comment='after unit association'):
            self.assertIsNotNone(repo2['last_unit_added'], repo2)

        # publish the second repo
        utils.publish_repo(self.cfg, repo2)
        repo2 = self.client.get(repo2['_href'], params={'details': True})
        with self.subTest(comment='after repository publish'):
            self.assertIsNotNone(repo2['last_unit_added'], repo2)
