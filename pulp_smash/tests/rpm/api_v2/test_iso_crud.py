# coding=utf-8
"""Test CRUD for ISO RPM repositories."""
from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import requests
import unittest2
from packaging.version import Version

from pulp_smash import config, constants, utils


_DISTRIBUTOR = {
    'distributor_id': 'iso_distributor',
    'distributor_type_id': 'iso_distributor',
    'distributor_config': {},
    'auto_publish': True
}
_IMPORTER_TYPE_ID = 'iso_importer'

_ISO_IMPORTER = {
    '_href': '/pulp/api/v2/repositories/{}/importers/iso_importer/',
    'id': 'iso_importer',
    'importer_type_id': 'iso_importer',
}
_ISO_DISTRIBUTOR = {
    '_href': '/pulp/api/v2/repositories/{}/distributors/iso_distributor/',
    'auto_publish': True,
    'config': {},
    'distributor_type_id': 'iso_distributor',
    'id': 'iso_distributor',
    'last_publish': None,
}


def _customize_href(template, repository_id):
    """Copy ``template`` and interpolate a repository ID into its ``_href``."""
    template = template.copy()
    template['_href'] = template['_href'].format(repository_id)
    return template


class _BaseTestCase(unittest2.TestCase):
    """Provide a server config, and tear down created resources."""

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an empty set of resources to delete."""
        cls.cfg = config.get_config()
        cls.resources = set()  # a set of _href paths

    @classmethod
    def tearDownClass(cls):
        """For each resource in ``cls.resources``, delete that resource."""
        for resource in cls.resources:
            utils.delete(cls.cfg, resource)


class CreateTestCase(_BaseTestCase):
    """Create an ISO RPM repo with an importer and distributor."""

    @classmethod
    def setUpClass(cls):
        """Create an ISO RPM repo with an importer and distributor."""
        super(CreateTestCase, cls).setUpClass()
        cls.body = {
            'description': utils.uuid4(),
            'display_name': utils.uuid4(),
            'distributors': [_DISTRIBUTOR],
            'id': utils.uuid4(),
            'importer_config': {},
            'importer_type_id': _IMPORTER_TYPE_ID,
            'notes': {utils.uuid4(): utils.uuid4()},
        }
        responses = []
        cls.attrs = utils.create_repository(cls.cfg, cls.body, responses)
        cls.response = responses[0]  # `responses` only has one element

    def test_status_code(self):
        """Assert the response has an HTTP 201 status code."""
        self.assertEqual(self.response.status_code, 201)

    def test_headers_location(self):
        """Assert the response's Location header is correct."""
        path = constants.REPOSITORY_PATH + self.body['id'] + '/'
        self.assertEqual(
            self.response.headers['Location'],
            urljoin(self.cfg.base_url, path)
        )

    def test_attributes(self):
        """Assert the created repository has the requested attributes."""
        # Pulp doesn't tell us about these attrs, despite us setting them.
        body = self.body.copy()
        for attr in {'importer_type_id', 'importer_config', 'distributors'}:
            del body[attr]

        # First check attrs are present, then check values for attrs we set.
        self.assertLessEqual(set(body.keys()), set(self.attrs.keys()))
        attrs = {key: self.attrs[key] for key in body.keys()}
        self.assertEqual(body, attrs)


class ReadUpdateDeleteTestCase(_BaseTestCase):
    """Establish that we can interact with typed repositories as expected."""

    @classmethod
    def setUpClass(cls):
        """Create three repositories and read, update and delete them."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()

        # Create repositories.
        cls.bodies = {
            'read': {
                'distributors': [_DISTRIBUTOR],
                'id': utils.uuid4(),
                'importer_config': {},
                'importer_type_id': _IMPORTER_TYPE_ID,
                'notes': {'this': 'one'},
            },
            'update': {  # like read, minus notes…
                'description': utils.uuid4(),  # plus this
                'display_name': utils.uuid4(),  # and this
                'distributors': [_DISTRIBUTOR],
                'id': utils.uuid4(),
                'importer_config': {},
                'importer_type_id': _IMPORTER_TYPE_ID,
            },
            'delete': {  # like read…
                'description': utils.uuid4(),  # plus this
                'display_name': utils.uuid4(),  # and this
                'distributors': [_DISTRIBUTOR],
                'id': utils.uuid4(),
                'importer_config': {},
                'importer_type_id': _IMPORTER_TYPE_ID,
                'notes': {utils.uuid4(): utils.uuid4()},
            },
        }
        cls.update_body = {'delta': {
            key: utils.uuid4() for key in ('description', 'display_name')
        }}
        hrefs = {
            key: utils.create_repository(cls.cfg, body)['_href']
            for key, body in cls.bodies.items()
        }
        cls.resources.update({hrefs[key] for key in {'read', 'update'}})

        # Read, update and delete them.
        cls.responses = {}
        cls.responses['read'] = requests.get(
            urljoin(cls.cfg.base_url, hrefs['read']),
            **cls.cfg.get_requests_kwargs()
        )
        for key in {'importers', 'distributors', 'details'}:
            path = '{}?{}=true'.format(hrefs['read'], key)
            cls.responses['read_' + key] = requests.get(
                urljoin(cls.cfg.base_url, path),
                **cls.cfg.get_requests_kwargs()
            )
        cls.responses['update'] = requests.put(
            urljoin(cls.cfg.base_url, hrefs['update']),
            json=cls.update_body,
            **cls.cfg.get_requests_kwargs()
        )
        cls.responses['delete'] = requests.delete(
            urljoin(cls.cfg.base_url, hrefs['delete']),
            **cls.cfg.get_requests_kwargs()
        )

    def test_status_code(self):
        """Assert each response has a correct HTTP status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                status_code = 202 if key == 'delete' else 200
                self.assertEqual(response.status_code, status_code)

    def test_read(self):
        """Assert that the "read" call returns correct attributes."""
        # Pulp doesn't tell us about these attrs, despite us setting them.
        body = self.bodies['read'].copy()
        for attr in {'importer_type_id', 'importer_config', 'distributors'}:
            del body[attr]

        # First check attrs are present, then check values for attrs we set.
        attrs = self.responses['read'].json()
        self.assertLessEqual(set(body.keys()), set(attrs.keys()))
        attrs = {key: attrs[key] for key in body.keys()}
        self.assertEqual(body, attrs)

    def test_read_importers(self):
        """Assert each read with importers contains info about importers."""
        for key in {'read_importers', 'read_details'}:
            with self.subTest(key=key):
                attrs = self.responses[key].json()
                self.assertIn('importers', attrs)
                self.assertEqual(len(attrs['importers']), 1)

                want = _customize_href(_ISO_IMPORTER, attrs['id'])
                have = attrs['importers'][0]
                self.assertLessEqual(set(want.keys()), set(have.keys()))
                have = {key: have[key] for key in want.keys()}
                self.assertEqual(want, have)

    def test_read_distributors(self):
        """Assert each read w/distributors contains info about distributors."""
        if self.cfg.version < Version('2.8') and utils.bug_is_untestable(1452):
            self.skipTest('https://pulp.plan.io/issues/1452')
        for key in {'read_distributors', 'read_details'}:
            with self.subTest(key=key):
                attrs = self.responses[key].json()
                self.assertIn('distributors', attrs)
                self.assertEqual(len(attrs['distributors']), 1)

                want = _customize_href(_ISO_DISTRIBUTOR, attrs['id'])
                have = attrs['distributors'][0]
                self.assertLessEqual(set(want.keys()), set(have.keys()))
                have = {key: have[key] for key in want.keys()}
                self.assertEqual(want, have)
