# coding=utf-8
"""Test unassociation of RPM unit types.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
`pulp_smash.tests.platform.api_v2.test_sync_publish` hold true.

http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/content/associate.html#unassociating-content-units-from-a-repository
"""

from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo


def _remove_unit(client, repo_href, type_id, unit_id):
    """Remove a unit from a repository.

    :param pulp_smash.api.Client client: object to make calls to API
    :param repo_href: url of the repo the unit is associated to
    :param type_id: type of unit that will be removed
    :param unit_id: id of the unit to be removed
    :return: response from server
    """
    rm_path = urljoin(repo_href, 'actions/unassociate/')
    if type_id is 'rpm':
        search_field = 'name'
    else:
        search_field = 'id'

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
    search_path = urljoin(repo_href, 'search/units/')
    search_body = {
        'criteria': {'type_ids': [type_id], 'filters': {'unit': {}}}
    }
    response = client.post(search_path, search_body)
    if type_id is 'rpm':
        return [unit['metadata']['name'] for unit in response]
    else:
        return [unit['metadata']['id'] for unit in response]


class RemoveAssociatedUnits(utils.BaseAPITestCase):
    """Remove units of various types from a synced RPM repository."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM, sync it, and remove some units."""
        super(RemoveAssociatedUnits, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        sync_path = urljoin(repo['_href'], 'actions/sync/')
        client.post(sync_path, {'override_config': {}})
        cls.repo = client.get(repo['_href'])
        cls.resources.add(repo['_href'])

        cls.testable_types = ['package_category', 'erratum', 'package_group',
                              'rpm']

        # List starting content
        cls.before_units = {
            type_id: _list_repo_units_of_type(client, repo['_href'], type_id)
            for type_id in cls.testable_types
        }

        # Remove one of each unit and store its id for later assertions
        cls.removed_units = {}
        for type_id, units_list in cls.before_units.items():
            cls.removed_units[type_id] = units_list[0]
            _remove_unit(client, repo['_href'], type_id, units_list[0])

        # List final content
        cls.after_units = {
            type_id: _list_repo_units_of_type(client, repo['_href'], type_id)
            for type_id in cls.testable_types
        }

    def test_units_removed(self):
        """Ensure that the specified units have been removed."""
        for type_id in self.testable_types:
            self.assertTrue(
                self.removed_units[type_id] in self.before_units[type_id]
            )
            self.assertFalse(
                self.removed_units[type_id] in self.after_units[type_id]
            )
            self.assertEqual(len(self.before_units[type_id]) - 1,
                             len(self.after_units[type_id]))
