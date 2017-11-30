# coding=utf-8
"""Test CRUD for ISO RPM repositories."""
import csv
import json
import unittest
from unittest import SkipTest
from urllib.parse import urljoin, urlparse

import requests
from packaging.version import Version

from pulp_smash import api, config, exceptions, selectors, utils
from pulp_smash.constants import (
    FILE_FEED_URL,
    FILE_MIXED_FEED_URL,
    FILE2_FEED_URL,
)
from pulp_smash.tests.pulp2.constants import REPOSITORY_PATH
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


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


def _gen_iso_repo(feed_url):
    """Generate a request body for creating a iso repository.

    :param feed_url: The feed URL where the repository will pull the
        contents
    """
    return {
        'distributors': [_DISTRIBUTOR],
        'id': utils.uuid4(),
        'importer_config': {'feed': feed_url},
        'importer_type_id': 'iso_importer',
    }


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
        # pylint:disable=line-too-long
        """Assert the response's ``Location`` header is correct.

        The ``Location`` may be either an absolute or relative URL. See
        :meth:`pulp_smash.tests.pulp2.platform.api_v2.test_repository.CreateSuccessTestCase.test_location_header`.
        """
        actual_path = urlparse(self.response.headers['Location']).path
        expect_path = urljoin(REPOSITORY_PATH, self.body['id'] + '/')
        self.assertEqual(actual_path, expect_path)

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
        if (self.cfg.pulp_version < Version('2.8') and
                selectors.bug_is_untestable(1452, self.cfg.pulp_version)):
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
      <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#associate-an-importer-to-a-repository>`_
    * `Associate a Distributor with a Repository
      <http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#associate-a-distributor-with-a-repository>`_
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
        if (cls.cfg.pulp_version >= Version('2.10') and
                selectors.bug_is_untestable(2082, cls.cfg.pulp_version)):
            raise SkipTest('https://pulp.plan.io/issues/2082')

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


class PulpManifestTestCase(utils.BaseAPITestCase):
    """Ensure ISO repo properly handles PULP_MANIFEST information."""

    @staticmethod
    def parse_pulp_manifest(feed_url):
        """Parse PULP_MANIFEST information from ``feed_url``/PULP_MANIFEST.

        :param feed_url: The URL for the file feed. It will be joined with
            /PULP_MANIFEST in order to find the PULP_MANIFEST file.
        :return: A list of dicts mapping each PULP_MANIFEST row. The dict
            contains the keys name, checksum and size which represent the
            PULP_MANIFEST data.
        """
        pulp_manifest_url = urljoin(feed_url, 'PULP_MANIFEST')
        reader = csv.DictReader(
            requests.get(pulp_manifest_url).text.splitlines(),
            ('name', 'checksum', 'size'),
        )
        return list(reader)

    def test_valid_file_feed(self):
        """Create and sync a ISO repo from a file feed.

        Assert that the number of units synced is the same as PULP_MANIFEST
        lists.
        """
        pulp_manifest_count = len(self.parse_pulp_manifest(FILE_FEED_URL))
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, _gen_iso_repo(FILE_FEED_URL))
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(self.cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        self.assertEqual(repo['total_repository_units'], pulp_manifest_count)
        self.assertEqual(
            repo['content_unit_counts']['iso'], pulp_manifest_count)

    def test_invalid_file_feed(self):
        """Create and sync a ISO repo from an invalid file feed.

        Assert that the sync fails with the information that some units were
        not available.
        """
        if self.cfg.pulp_version < Version('2.11'):
            self.skipTest(
                'Pulp reports 404 for ISO repos only on 2.11 or greater.')
        pulp_manifest = self.parse_pulp_manifest(FILE_MIXED_FEED_URL)
        missing = [
            row['name'] for row in pulp_manifest
            if row['name'].startswith('missing')
        ]
        client = api.Client(self.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, _gen_iso_repo(FILE_MIXED_FEED_URL))
        self.addCleanup(client.delete, repo['_href'])
        with self.assertRaises(exceptions.TaskReportError) as context:
            utils.sync_repo(self.cfg, repo)
        task = context.exception.task
        self.assertIsNotNone(task['error'])
        # Description is a string generated after a Python's list of dicts
        # object. Adjust the string so we can parse it as JSON instead of using
        # eval. Having this as a Python object helps inspecting the message
        description = json.loads(
            task['error']['description']
            .replace('u\'', '\'')
            .replace('\'', '"')
        )
        for info in description:
            with self.subTest(name=info['name']):
                self.assertEqual(info['error']['response_code'], 404)
                self.assertEqual(info['error']['response_msg'], 'Not Found')
                self.assertIn(info['name'], missing)


class ISOUpdateTestCase(unittest.TestCase):
    """Verify how ISO repos handles changes in content already in Pulp."""

    def test_all(self):
        """Verify how ISO repos handles changes in content already in Pulp.

        The main goal of this test is to verify how ISO repository handles
        updates in content already in Pulp.

        For this test two different feed urls will be used. These urls contain
        the same amount of units, the units have the same type and name in both
        urls, but different content thereafter different checksum values. To
        recreate this dynamic scenario of change. After the repository is
        synced for the first time the feed url is updated, and the repository
        is synced again.

        This test targets the following issues:

        * `Pulp Smash #715 <https://github.com/PulpQE/pulp-smash/issues/715>`_
        * `Pulp #2773 <https://pulp.plan.io/issues/2773>`_
        * `Pulp #3047 <https://pulp.plan.io/issues/3047>`_
        * `Pulp #3100 <https://pulp.plan.io/issues/3100>`_

        Do the following:

        1. Create and sync an ISO repository.
        2. Update the repository's feed URL, and sync it. This simulates a
           change in the contents of the source ISOs.
        3. Assert that number of units remain the same, but the content has
           changed.
        """
        cfg = config.get_config()
        for issue_id in (2773, 3047, 3100):
            if selectors.bug_is_untestable(issue_id, cfg.pulp_version):
                self.skipTest('https://pulp.plan.io/issues/' + str(issue_id))

        # Step 1
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, _gen_iso_repo(FILE_FEED_URL))
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo)
        units_pre = utils.search_units(cfg, repo)

        # Step 2
        client.put(repo['importers'][0]['_href'], {
            'importer_config': {'feed': FILE2_FEED_URL}
        })
        utils.sync_repo(cfg, repo)
        units_post = utils.search_units(cfg, repo)

        # Step 3
        self.assertEqual(len(units_pre), len(units_post))
        self.check_names(units_pre, units_post)
        self.check_checksums(units_pre, units_post)

    def check_names(self, units_pre, units_post):
        """Assert that the names in units_pre and units_post are equal."""
        names_pre = {unit['metadata']['name'] for unit in units_pre}
        names_post = {unit['metadata']['name'] for unit in units_post}
        self.assertEqual(names_pre, names_post)

    def check_checksums(self, units_pre, units_post):
        """Assert the checksums in units_pre and units_post are disjoint."""
        checksums_pre = {unit['metadata']['checksum'] for unit in units_pre}
        checksums_post = {unit['metadata']['checksum'] for unit in units_post}
        self.assertEqual(checksums_pre - checksums_post, checksums_pre)
