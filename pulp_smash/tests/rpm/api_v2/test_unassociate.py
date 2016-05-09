# coding=utf-8
"""Test `Unassociating Content Units from a Repository`_ for RPM.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _Unassociating Content Units from a Repository:
   http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/associate.html#unassociating-content-units-from-a-repository
"""
from __future__ import unicode_literals

import random
import time

from dateutil.parser import parse

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_RPM_ID_FIELD = 'checksum'
# RPM units do not have an ``id`` metadata field. This is problematic when
# trying to select a specific RPM content unit, as the remaining metadata
# fields may be non-unique. For example, two different RPM content units may
# both have a name of "walrus" — they just provide different versions. This
# constant attempts to name a substitute for an ID.


def _get_unit_id(unit):
    """Return the unit's _RPM_ID_FIELD if an RPM. Otherwise, return ID."""
    if unit['unit_type_id'] == 'rpm':
        return unit['metadata'][_RPM_ID_FIELD]
    return unit['metadata']['id']


def _get_units_by_type(units, type_id):
    """Return a list of units having the given unit type ID."""
    return [unit for unit in units if unit['unit_type_id'] == type_id]


def _remove_unit(server_config, repo_href, unit):
    """Remove unit ``unit`` from the repository at ``repo_href``.

    Return the JSON-decoded response body.
    """
    path = urljoin(repo_href, 'actions/unassociate/')
    type_id = unit['unit_type_id']  # e.g. 'rpm'
    key = _RPM_ID_FIELD if type_id == 'rpm' else 'id'
    body = {'criteria': {
        'filters': {'unit': {key: unit['metadata'][key]}},
        'type_ids': [type_id],
    }}
    return api.Client(server_config).post(path, body).json()


def _search_units(server_config, repo_href, type_ids):
    """Find units of types ``type_ids`` in the repository at ``repo_href``.

    Return the JSON-decoded response body.
    """
    return api.Client(server_config).post(
        urljoin(repo_href, 'search/units/'),
        {'criteria': {'type_ids': type_ids}},
    ).json()


class RemoveUnitsTestCase(utils.BaseAPITestCase):
    """Remove units of various types from a synced RPM repository."""

    TYPE_IDS = [
        'erratum',
        'package_category',
        'package_group',
        'rpm',
    ]
    """IDs of unit types that can be removed from an RPM repository."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository, sync it, and remove some units from it.

        After creating and syncing an RPM repository, we walk through the unit
        type IDs listed in
        :data:`pulp_smash.tests.rpm.api_v2.test_unassociate.RemoveUnitsTestCase.TYPE_IDS`
        and remove on unit of each kind from the repository. We verify Pulp's
        behaviour by recording repository contents pre and post removal.
        """
        super(RemoveUnitsTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Remove one unit of each type.
        cls.units_before = _search_units(cls.cfg, repo['_href'], cls.TYPE_IDS)
        cls.units_removed = []
        for type_id in cls.TYPE_IDS:
            unit = random.choice(_get_units_by_type(cls.units_before, type_id))
            cls.units_removed.append(unit)
            _remove_unit(cls.cfg, repo['_href'], unit)
        cls.units_after = _search_units(cls.cfg, repo['_href'], cls.TYPE_IDS)

    def test_units_not_in_search(self):
        """Assert the removed units do not appear in search results."""
        ids_removed = {_get_unit_id(unit) for unit in self.units_removed}
        ids_after = {_get_unit_id(unit) for unit in self.units_after}
        self.assertEqual(ids_removed & ids_after, set())  # s1.isdisjoint(s2)

    def test_one_removal_per_unit_type(self):
        """Assert, for each unit type, that one unit has been removed."""
        for type_id in self.TYPE_IDS:
            with self.subTest(type_id=type_id):
                before = _get_units_by_type(self.units_before, type_id)
                after = _get_units_by_type(self.units_after, type_id)
                self.assertEqual(len(before) - 1, len(after))


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
        utils.sync_repo(cls.cfg, repo['_href'])

        # Add a distributor and publish the repository to it.
        path = urljoin(repo['_href'], 'distributors/')
        distributor = client.post(path, gen_distributor())
        path = urljoin(repo['_href'], 'actions/publish/')
        client.post(path, {'id': distributor['id']})

        # List RPM content units in the repository. Pick one and remove it.
        # NOTE: There are two versions of the "walrus" RPM, and this works even
        # when that name is picked.
        unit = random.choice(_search_units(cls.cfg, repo['_href'], ('rpm',)))
        cls.unit_id = _get_unit_id(unit)
        _remove_unit(cls.cfg, repo['_href'], unit)

        # Re-publish the repository. sleep() for test_compare_timestamps.
        # Re-read the repository so the test methods have fresh data.
        time.sleep(2)
        path = urljoin(repo['_href'], 'actions/publish/')
        client.post(path, {'id': distributor['id']})
        cls.repo = client.get(repo['_href'], params={'details': True})

    def test_get_removed_unit(self):
        """Verify the removed unit cannot be fetched."""
        units = _search_units(self.cfg, self.repo['_href'], ('rpm',))
        unit_ids = {_get_unit_id(unit) for unit in units}
        self.assertNotIn(self.unit_id, unit_ids)

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
