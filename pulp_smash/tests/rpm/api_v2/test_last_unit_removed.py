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
import time

import isodate

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    sync_repo,
)

_PUBLISH_DIR = 'pulp/repos/'


class LastDeletedTestCase(utils.BaseAPITestCase):
    """Test re-publish repository after unassociating content."""

    @classmethod
    def setUpClass(cls):
        """last_unit_removed and last_publish which should be timezone aware.

        Following steps are executed:

        1. Create repository foo with feed
        2. Remove rpm from repository
        4. Publish repository
        5. last_publish and last_unit_removed should be comparable
           (both offset-aware)
        """
        super(LastDeletedTestCase, cls).setUpClass()
        cls.responses = {}

        # Create and sync a repository.
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo_href = client.post(REPOSITORY_PATH, body).json()['_href']

        cls.resources.add(repo_href)  # mark for deletion
        cls.responses['sync'] = sync_repo(cls.cfg, repo_href)

        # Add a distributor and publish it.
        cls.responses['distribute'] = client.post(
            urljoin(repo_href, 'distributors/'),
            gen_distributor(),
        )

        body = {'criteria': {}}
        cls.responses['repo units'] = client.post(urljoin(repo_href,
                                                          'search/units/'),
                                                  body)

        # Get random unit from repository to remove
        removed_unit = random.choice([
            unit['metadata']['filename']
            for unit in cls.responses['repo units'].json()
            if unit['unit_type_id'] == 'rpm'
        ])

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
        time.sleep(1)

        # Publish the repo again
        cls.responses['publish'] = client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )

        cls.responses['repo'] = client.get(repo_href)

        cls.responses['distributor'] = client.get(
            urljoin(repo_href, 'distributors/',
                    cls.responses['distribute'].json()['id']),
        )

    def test_last_deleted(self):
        """Verify the HTTP status code of each publish."""
        repo = self.responses['repo'].json()
        last_unit_removed = isodate.parse_datetime(repo['last_unit_removed'])
        distributor = self.responses['distributor'].json()[0]
        last_publish = isodate.parse_datetime(distributor['last_publish'])
        self.assertLess(last_unit_removed, last_publish)
