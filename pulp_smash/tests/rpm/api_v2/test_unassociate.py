# coding=utf-8
"""Test `Unassociating Content Units from a Repository`_ for RPM.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _Unassociating Content Units from a Repository:
   http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/associate.html#unassociating-content-units-from-a-repository
"""
from __future__ import unicode_literals

import random
import time

from dateutil.parser import parse

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    sync_repo,
)


def _remove_unit(client, repo_href, type_id, unit_id):
    """Remove a unit from a repository.

    :param pulp_smash.api.Client client: object to make calls to API
    :param repo_href: url of the repo the unit is associated to
    :param type_id: type of unit that will be removed
    :param unit_id: id of the unit to be removed
    :return: response from server
    """
    rm_path = urljoin(repo_href, 'actions/unassociate/')
    search_field = 'name' if type_id == 'rpm' else 'id'
    rm_body = {
        'criteria': {
            'type_ids': [type_id], 'filters': {
                'unit': {search_field: {'$in': [unit_id]}}
            }
        }
    }
    return client.post(rm_path, rm_body)


def _list_repo_units_of_type(client, repo_href, type_id):
    """List units of the specified type in the repository at the href.

    :param pulp_smash.api.Client client: object to make calls to API
    :param repo_href: url of the repo the unit is associated to
    :param type_id: type of unit that will be removed
    :return: list of unit identifiers
    """
    response = client.post(
        urljoin(repo_href, 'search/units/'),
        {'criteria': {'type_ids': [type_id], 'filters': {'unit': {}}}},
    )
    key = 'name' if type_id == 'rpm' else 'id'
    return [unit['metadata'][key] for unit in response]


class RemoveAssociatedUnits(utils.BaseAPITestCase):
    """Remove units of various types from a synced RPM repository."""

    TYPE_IDS = {
        'erratum',
        'package_category',
        'package_group',
        'rpm',
    }
    """IDs of unit types that can be removed from an RPM repository."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository, sync it, and remove some units from it.

        After creating and syncing an RPM repository, we walk through the unit
        type IDs listed in
        :data:`pulp_smash.tests.rpm.api_v2.test_unassociate.RemoveAssociatedUnits.TYPE_IDS`
        and remove on unit of each kind from the repository. We verify Pulp's
        behaviour by recording repository contents pre and post removal.
        """
        super(RemoveAssociatedUnits, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])
        sync_path = urljoin(repo['_href'], 'actions/sync/')
        client.post(sync_path, {'override_config': {}})

        # List starting content
        cls.before_units = {
            type_id: _list_repo_units_of_type(client, repo['_href'], type_id)
            for type_id in cls.TYPE_IDS
        }

        # Remove one of each unit and store its id for later assertions
        cls.removed_units = {}
        for type_id, units_list in cls.before_units.items():
            cls.removed_units[type_id] = units_list[0]
            _remove_unit(client, repo['_href'], type_id, units_list[0])

        # List final content
        cls.after_units = {
            type_id: _list_repo_units_of_type(client, repo['_href'], type_id)
            for type_id in cls.TYPE_IDS
        }

    def test_units_before_removal(self):
        """Assert the removed units are present before the removal."""
        for type_id in self.TYPE_IDS:
            with self.subTest(type_id=type_id):
                self.assertIn(
                    self.removed_units[type_id],
                    self.before_units[type_id],
                )

    def test_units_after_removal(self):
        """Assert the removed units are not present after the removal."""
        for type_id in self.TYPE_IDS:
            with self.subTest(type_id=type_id):
                self.assertNotIn(
                    self.removed_units[type_id],
                    self.after_units[type_id],
                )

    def test_one_unit_removed(self):
        """Assert, for each unit type, that one unit has been removed."""
        for type_id in self.TYPE_IDS:
            with self.subTest(type_id=type_id):
                self.assertEqual(
                    len(self.before_units[type_id]) - 1,
                    len(self.after_units[type_id])
                )


class RemoveAndRepublishTestCase(utils.BaseAPITestCase):
    """Publish a repository, remove a unit, and publish it again.

    The removed unit should be inaccessible after the repository is published a
    second time. In addition, repository and distributor timestamps should be
    updated accordingly.
    """

    @classmethod
    def setUpClass(cls):
        """Publish a repository, remove a unit, and publish it again.

        Specifically, do the following:

        1. Create a repository with a feed and sync it.
        2. Add a distributor to the repository and publish the repository.
        3. Select a content unit at random. Remove it from the repository, and
           re-publish the repository.
        """
        super(RemoveAndRepublishTestCase, cls).setUpClass()

        # Create and sync a repository.
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])  # mark for deletion
        sync_repo(cls.cfg, repo['_href'])

        # Add a distributor and publish the repository to it.
        path = urljoin(repo['_href'], 'distributors/')
        distributor = client.post(path, gen_distributor())
        path = urljoin(repo['_href'], 'actions/publish/')
        client.post(path, {'id': distributor['id']})

        # List RPM content units in the repository. Pick one and remove it.
        # NOTE: There are two versions of the "walrus" RPM, and this works even
        # when that name is picked.
        path = urljoin(repo['_href'], 'search/units/')
        units = client.post(path, {'criteria': {'type_ids': ['rpm']}})
        cls.unit_name = random.choice([
            unit['metadata']['name'] for unit in units
        ])
        body = {'criteria': {
            'filters': {'unit': {'name': cls.unit_name}},
            'type_ids': ['rpm'],
        }}
        client.post(urljoin(repo['_href'], 'actions/unassociate/'), body)

        # Re-publish the repository. sleep() for test_compare_timestamps.
        # Re-read the repository so the test methods have fresh data.
        time.sleep(2)
        path = urljoin(repo['_href'], 'actions/publish/')
        client.post(path, {'id': distributor['id']})
        cls.repo = client.get(repo['_href'], params={'details': True})

    def test_get_removed_unit(self):
        """Verify the removed unit cannot be fetched."""
        units = api.Client(self.cfg).post(
            urljoin(self.repo['_href'], 'search/units/'),
            {'criteria': {'type_ids': ['rpm']}},
        ).json()
        unit_names = {unit['metadata']['name'] for unit in units}
        self.assertNotIn(self.unit_name, unit_names)

    def test_compare_timestamps(self):
        """Verify the repository and distributor timestamps are corrects.

        Specifically, the repository's ``last_unit_removed`` time should be
        before the distributor's ``last_publish`` time. Times returned by Pulp
        are accurate to the nearest second, and it is possible that the process
        of publishing a repository could take less than one second. To ensure
        the times differ, :meth:`setUpClass` waits one second between the
        removal and second publication.
        """
        last_unit_removed = parse(self.repo['last_unit_removed'])
        self.assertEqual(len(self.repo['distributors']), 1)
        last_publish = parse(self.repo['distributors'][0]['last_publish'])
        self.assertLess(last_unit_removed, last_publish)
