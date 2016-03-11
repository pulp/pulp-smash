# coding=utf-8
"""Test CRUD for ISO RPM repositories."""
from __future__ import unicode_literals

from packaging.version import Version

from pulp_smash import api, selectors, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH


_DISTRIBUTOR = {
    'distributor_id': 'iso_distributor',
    'distributor_type_id': 'iso_distributor',
    'distributor_config': {},
    'auto_publish': True
}
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


def _customize_template(template, repository_id):
    """Copy ``template`` and interpolate a repository ID into its ``_href``."""
    template = template.copy()
    template['_href'] = template['_href'].format(repository_id)
    return template


class CreateTestCase(utils.BaseAPITestCase):
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
            'importer_type_id': 'iso_importer',
            'notes': {utils.uuid4(): utils.uuid4()},
        }
        cls.response = api.Client(cls.cfg).post(REPOSITORY_PATH, cls.body)

    def test_status_code(self):
        """Assert the response has an HTTP 201 status code."""
        self.assertEqual(self.response.status_code, 201)

    def test_headers_location(self):
        """Assert the response's Location header is correct."""
        path = REPOSITORY_PATH + self.body['id'] + '/'
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
        attrs = self.response.json()
        self.assertLessEqual(set(body.keys()), set(attrs.keys()))
        attrs = {key: attrs[key] for key in body.keys()}
        self.assertEqual(body, attrs)


class ReadUpdateDeleteTestCase(utils.BaseAPITestCase):
    """Establish that we can interact with typed repositories as expected."""

    @classmethod
    def setUpClass(cls):
        """Create three repositories and read, update and delete them."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()
        cls.bodies = {
            'read': {
                'distributors': [_DISTRIBUTOR],
                'id': utils.uuid4(),
                'importer_config': {},
                'importer_type_id': 'iso_importer',
                'notes': {'this': 'one'},
            },
            'update': {  # like read, minus notes…
                'description': utils.uuid4(),  # plus this
                'display_name': utils.uuid4(),  # and this
                'distributors': [_DISTRIBUTOR],
                'id': utils.uuid4(),
                'importer_config': {},
                'importer_type_id': 'iso_importer',
            },
            'delete': {  # like read…
                'description': utils.uuid4(),  # plus this
                'display_name': utils.uuid4(),  # and this
                'distributors': [_DISTRIBUTOR],
                'id': utils.uuid4(),
                'importer_config': {},
                'importer_type_id': 'iso_importer',
                'notes': {utils.uuid4(): utils.uuid4()},
            },
        }
        cls.update_body = {'delta': {
            key: utils.uuid4() for key in ('description', 'display_name')
        }}
        cls.responses = {}

        # Create repositories.
        client = api.Client(cls.cfg, api.json_handler)
        repos = {
            key: client.post(REPOSITORY_PATH, body)
            for key, body in cls.bodies.items()
        }
        for key in {'read', 'update'}:
            cls.resources.add(repos[key]['_href'])

        # Read, update and delete the repositories.
        client.response_handler = api.safe_handler
        cls.responses['read'] = client.get(repos['read']['_href'])
        for key in {'importers', 'distributors', 'details'}:
            cls.responses['read_' + key] = client.get(
                repos['read']['_href'],
                params={key: True},
            )
        cls.responses['update'] = client.put(
            repos['update']['_href'],
            cls.update_body,
        )
        cls.responses['delete'] = client.delete(repos['delete']['_href'])

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

                want = _customize_template(_ISO_IMPORTER, attrs['id'])
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

                want = _customize_template(_ISO_DISTRIBUTOR, attrs['id'])
                have = attrs['distributors'][0]
                self.assertLessEqual(set(want.keys()), set(have.keys()))
                have = {key: have[key] for key in want.keys()}
                self.assertEqual(want, have)


class AddImporterDistributorTestCase(utils.BaseAPITestCase):
    """Add an importer and a distributor to an existing untyped repository.

    See:

    * `Associate an Importer to a Repository
      <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#associate-an-importer-to-a-repository>`_
    * `Associate a Distributor with a Repository
      <http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#associate-a-distributor-with-a-repository>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository and add an importer and distributor to it.

        Do the following:

        1. Create a repository.
        2. Read the repository's importers and distributors.
        3. Add an importer and distributor to the repo.
        4. Re-read the repository's importers and distributors.
        """
        super(AddImporterDistributorTestCase, cls).setUpClass()

        # Steps 1 and 2.
        client = api.Client(cls.cfg, api.json_handler)
        href = client.post(REPOSITORY_PATH, {'id': utils.uuid4()})['_href']
        cls.resources.add(href)
        cls.pre_imp = client.get(urljoin(href, 'importers/'))
        cls.pre_dist = client.get(urljoin(href, 'distributors/'))

        # Steps 3 and 4.
        client.response_handler = api.safe_handler
        cls.add_imp = client.post(
            urljoin(href, 'importers/'),
            {'importer_type_id': 'iso_importer'},
        )
        cls.add_dist = client.post(
            urljoin(href, 'distributors/'),
            {
                'distributor_config': {},
                'distributor_id': utils.uuid4(),
                'distributor_type_id': 'iso_distributor',
            },
        )
        client.response_handler = api.json_handler
        cls.post_imp = client.get(urljoin(href, 'importers/'))
        cls.post_dist = client.get(urljoin(href, 'distributors/'))

    def test_add_importer(self):
        """Check the HTTP status code for adding an importer."""
        self.assertEqual(self.add_imp.status_code, 202)

    def test_add_distributor(self):
        """Check the HTTP status code for adding a distributor."""
        self.assertEqual(self.add_dist.status_code, 201)

    def test_before(self):
        """Verify the repository has no importer or distributors initially."""
        for i, attrs in enumerate((self.pre_imp, self.pre_dist)):
            with self.subTest(i=i):
                self.assertEqual(len(attrs), 0, attrs)

    def test_after(self):
        """Verify the repository ends up with one importer and distributor."""
        for i, attrs in enumerate((self.post_imp, self.post_dist)):
            with self.subTest(i=i):
                self.assertEqual(len(attrs), 1, attrs)
