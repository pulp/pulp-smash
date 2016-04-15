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

import random

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


class RepublishTestCase(utils.BaseAPITestCase):
    """Test re-publish repository after unassociating content."""

    @classmethod
    def setUpClass(cls):
        """Create one repository with feed, unassociate unit and re-publish.

        Following steps are executed:

        1. Create repository foo with feed, sync and publish it.
        2. Get an unit X and assert it is accessible.
        3. Remove unit X from repository foo and re-publish foo.
        4. Get same unit X and assert it is not accessible.
        """
        super(RepublishTestCase, cls).setUpClass()
        cls.responses = {}

        # Create and sync a repository.
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']
        cls.resources.add(repo_href)  # mark for deletion
        cls.responses['sync'] = utils.sync_repo(cls.cfg, repo_href)

        # Add a distributor and publish it.
        cls.responses['distribute'] = client.post(
            urljoin(repo_href, 'distributors/'),
            gen_distributor(),
        )
        cls.responses['first publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )

        # Get contents of repository
        cls.responses['repo units'] = client.post(
            urljoin(repo_href, 'search/units/'),
            {'criteria': {}},
        )

        # Get random unit from repository to remove
        removed_unit = random.choice([
            unit['metadata']['filename']
            for unit in cls.responses['repo units'].json()
            if unit['unit_type_id'] == 'rpm'
        ])

        # Download the RPM from repository.
        url = urljoin(
            '/pulp/repos/',
            cls.responses['distribute'].json()['config']['relative_url']
        )
        url = urljoin(url, removed_unit)
        cls.responses['first get'] = client.get(url)

        # Remove unit from the repo
        cls.responses['remove unit'] = client.post(
            urljoin(repo_href, 'actions/unassociate/'),
            {
                'criteria': {
                    'fields': {
                        'unit': [
                            'arch',
                            'checksum',
                            'checksumtype',
                            'epoch',
                            'name',
                            'release',
                            'version',
                        ]
                    },
                    'type_ids': ['rpm'],
                    'filters': {
                        'unit': {'filename': removed_unit}
                    }
                }
            },
        )

        # Publish the repo again
        cls.responses['second publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )

        # Download the RPM from repository.
        url = urljoin(
            '/pulp/repos/',
            cls.responses['distribute'].json()['config']['relative_url']
        )
        url = urljoin(url, removed_unit)
        client.response_handler = api.echo_handler
        cls.responses['second get'] = client.get(url)

    def test_publishes_succeed(self):
        """Verify the HTTP status code of each publish."""
        for step, code in (
                ('first publish', 202),
                ('second publish', 202),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)

    def test_rpm_can_be_accessed(self):
        """Test rpm can be accessed after first publish."""
        self.assertEqual(self.responses['first get'].status_code, 200)

    def test_rpm_cannot_be_accessed(self):
        """Test rpm cannot be accessed after its removal and re-publish."""
        self.assertEqual(self.responses['second get'].status_code, 404)
