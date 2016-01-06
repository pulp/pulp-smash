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

from pulp_smash import config, constants, selectors, utils


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
        if (self.cfg.version < Version('2.8') and
                selectors.bug_is_untestable(1452)):
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


def _add_importer(server_config, href, json):
    """Add an importer to a repository and wait for the task to complete."""
    url = urljoin(server_config.base_url, href)
    url = urljoin(url, 'importers/')
    response = requests.post(
        url,
        json=json,
        **server_config.get_requests_kwargs()
    )
    response.raise_for_status()
    if response.status_code == 202:
        utils.poll_spawned_tasks(server_config, response.json())
    return response


def _add_distributor(server_config, href, json):
    """Add a distributor to a repository."""
    url = urljoin(server_config.base_url, href)
    url = urljoin(url, 'distributors/')
    response = requests.post(
        url,
        json=json,
        **server_config.get_requests_kwargs()
    )
    response.raise_for_status()
    return response


class AddImporterDistributorTestCase(_BaseTestCase):
    """Add an importer and a distributor to an existing untyped repository.

    See:

    * `Associate an Importer to a Repository
      <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#associate-an-importer-to-a-repository>`_
    * `Associate a Distributor with a Repository
      <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#associate-a-distributor-with-a-repository>`_


    """

    @classmethod
    def setUpClass(cls):
        """Create a repository and add an importer and distributor to it."""
        # Create a repository.
        super(AddImporterDistributorTestCase, cls).setUpClass()
        href = utils.create_repository(cls.cfg, {'id': utils.uuid4()})['_href']
        cls.resources.add(href)

        # Read importers and distributors.
        cls.imp_before = utils.get_importers(cls.cfg, href)
        cls.distrib_before = utils.get_distributors(cls.cfg, href)

        # Add an importer and a distributor.
        cls.responses = {}
        cls.responses['add importer'] = _add_importer(
            cls.cfg,
            href,
            {'importer_type_id': _IMPORTER_TYPE_ID},
        )
        cls.responses['add distributor'] = _add_distributor(
            cls.cfg,
            href,
            {
                'distributor_config': {},
                'distributor_id': utils.uuid4(),
                'distributor_type_id': 'iso_distributor',
            },
        )

        # Read importers and distributors again.
        cls.imp_after = utils.get_importers(cls.cfg, href)
        cls.distrib_after = utils.get_distributors(cls.cfg, href)

    def test_add_importer(self):
        """Check the HTTP status code for adding an importer."""
        self.assertEqual(self.responses['add importer'].status_code, 202)

    def test_add_distributor(self):
        """Check the HTTP status code for adding a distributor."""
        self.assertEqual(self.responses['add distributor'].status_code, 201)

    def test_before(self):
        """Check the repository's importers and distributors before adding any.

        By default, the repository should have zero of each.
        """
        for i, attrs in enumerate((self.imp_before, self.distrib_before)):
            with self.subTest(i=i):
                self.assertEqual(len(attrs), 0, attrs)

    def test_after(self):
        """Check the repository's importers and distributors after adding any.

        The repository should have one of each.
        """
        for i, attrs in enumerate((self.imp_after, self.distrib_after)):
            with self.subTest(i=i):
                self.assertEqual(len(attrs), 1, attrs)
