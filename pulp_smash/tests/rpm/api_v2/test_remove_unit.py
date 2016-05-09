# coding=utf-8
"""Test the functionality in RPM repos when `remove_missing`_ is set to True.

Following steps are executed in order to test correct functionality
of repository created with valid feed and remove_missing option set.

1. Create repository foo with valid feed, run sync, add distributor to it and
   publish over http and https.
2. Create second repository bar, with feed pointing to first repository, set
   ``remove_missing=True`` and run sync on them.
3. Assert that repositories contain same set of units.
4. Remove random unit from repository foo and publish.
5. Sync bar repository.
6. Assert that both repositories contain same units.

.. _remove_missing:
    https://pulp-rpm.readthedocs.io/en/latest/tech-reference/yum-plugins.html
"""

from __future__ import unicode_literals

import random

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


def _get_rpm_ids(search_body):
    """Get RPM unit IDs from search results. Return a set."""
    return {
        unit['unit_id'] for unit in search_body
        if unit['unit_type_id'] == 'rpm'
    }


class RemoveMissingTestCase(utils.BaseAPITestCase):
    """Test functionality of --remove-missing option enabled."""

    @classmethod
    def setUpClass(cls):
        """Create two repositories, first is feed of second one.

        Provides server config and set of iterable to delete. Following steps
        are executed:

        1. Create repository foo with feed, sync and publish it.
        2. Create repository bar with foo as a feed and run sync.
        3. Get content of both repositories.
        4. Remove random unit from repository foo and publish foo.
        5. Sync repository bar.
        6. Get content of both repositories.
        """
        super(RemoveMissingTestCase, cls).setUpClass()
        cls.responses = {}
        hrefs = []  # repository hrefs

        # Create and sync a repository.
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        hrefs.append(client.post(REPOSITORY_PATH, body).json()['_href'])
        cls.resources.add(hrefs[0])  # mark for deletion
        cls.responses['first sync'] = utils.sync_repo(cls.cfg, hrefs[0])

        # Add a distributor and publish it.
        cls.responses['distribute'] = client.post(
            urljoin(hrefs[0], 'distributors/'),
            gen_distributor(),
        )
        cls.responses['first publish'] = client.post(
            urljoin(hrefs[0], 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )

        # Create and sync a second repository. We disable SSL validation for a
        # practical reason: each HTTPS feed must have a certificate to work,
        # which is burdensome to do here.
        body = gen_repo()
        body['importer_config']['feed'] = urljoin(
            cls.cfg.base_url,
            _PUBLISH_DIR +
            cls.responses['distribute'].json()['config']['relative_url'],
        )
        body['importer_config']['remove_missing'] = True  # see docstring
        body['importer_config']['ssl_validation'] = False
        hrefs.append(client.post(REPOSITORY_PATH, body).json()['_href'])
        cls.resources.add(hrefs[1])  # mark for deletion
        cls.responses['second sync'] = utils.sync_repo(cls.cfg, hrefs[1])

        # Get contents of both repositories
        for i, href in enumerate(hrefs):
            cls.responses['repo {} units, pre'.format(i)] = client.post(
                urljoin(href, 'search/units/'),
                {'criteria': {}},
            )

        # Get random unit from first repository to remove
        cls.removed_unit = random.choice([
            unit['metadata']['name']
            for unit in cls.responses['repo 0 units, pre'].json()
            if unit['unit_type_id'] == 'rpm'
        ])

        # Remove unit from first repo and publish again
        cls.responses['remove unit'] = client.post(
            urljoin(hrefs[0], 'actions/unassociate/'),
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
                        'unit': {'name': cls.removed_unit}
                    }
                }
            },
        )

        # Publish the first repo again, and sync the second repo again.
        cls.responses['second publish'] = client.post(
            urljoin(hrefs[0], 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )
        cls.responses['third sync'] = utils.sync_repo(cls.cfg, hrefs[1])

        # Search for units in both repositories again
        for i, href in enumerate(hrefs):
            cls.responses['repo {} units, post'.format(i)] = client.post(
                urljoin(href, 'search/units/'),
                {'criteria': {}},
            )

    def test_status_code(self):
        """Verify the HTTP status code of each server response."""
        for step, code in (
                ('first sync', 202),
                ('second sync', 202),
                ('third sync', 202),
                ('first publish', 202),
                ('second publish', 202),
                ('repo 0 units, pre', 200),
                ('repo 1 units, pre', 200),
                ('repo 0 units, post', 200),
                ('repo 1 units, post', 200),
                ('distribute', 201),
                ('remove unit', 202),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)

    def test_units_before_removal(self):
        """Assert the repositories have the same units before the removal.

        Package category and package group differ, so we count only RPM units.
        """
        self.assertEqual(
            _get_rpm_ids(self.responses['repo 0 units, pre'].json()),
            _get_rpm_ids(self.responses['repo 1 units, pre'].json()),
        )

    def test_units_after_removal(self):
        """Assert the repositories have the same units after the removal.

        Package category and package group differ, so we count only RPM units.
        """
        self.assertEqual(
            _get_rpm_ids(self.responses['repo 0 units, post'].json()),
            _get_rpm_ids(self.responses['repo 1 units, post'].json()),
        )

    def test_unit_removed(self):
        """Test that correct unit from first repository has been removed."""
        body = self.responses['repo 0 units, post'].json()
        units_names = set(
            unit['metadata']['name'] for unit in body
            if unit['unit_type_id'] == 'rpm'
        )
        self.assertNotIn(self.removed_unit, units_names)
