# coding=utf-8
"""Test the `repository`_ API endpoints.

The assumptions explored in this module have the following dependencies::

        It is possible to create an untyped repository.
        ├── It is impossible to create a repository with a duplicate ID
        │   or other invalid attributes.
        ├── It is possible to read a repository.
        │    ├── it is possible to view an empty list of distributors as part
        │    │     of a repo
        │    └── it is possible to view an empty list of importers as
        │          part of a repo
        ├── It is possible to update a repository.
        ├── It is possible to delete a repository.
        ├── It is possible to create a typed repo (with importers and
        │    distributors)
        │   ├─── it is possible to read distributors of a repo (via repo call)
        │   ├─── it is possible to read importers of a repo (via repo call)
        │   ├─── it is possible to read distributors of a repo (via
        │   │      distributors call)
        │   ├─── it is possible to read importers of a repo (via
        │   │      importers call)
        │   ├─── it is possible to read an individual distributor of a repo
        │   │      (via distributor call)
        │   └─── it is possible to read an individual importer of a repo
        │         (via importer call)
        ├── It is possible to add a distributor to an untyped repo
        │   ├─── it is possible to read distributors of a repo (via repo call)
        │   ├─── it is possible to read distributors of a repo
        │   │      (via distributors call)
        │   ├─── it is possible to read an individual distributor of a repo
        │   │      (via distributor call)
        │   ├─── It is possible to update a distributor on a repo.
        │   │    └─── it is possible to read the updated distributor
        │   └─── It is possible to delete a distributor from a repo.
        └── It is possible to add an importer to an untyped repo
            ├─── it is possible to read importers of a repo (via repo call)
            ├─── it is possible to read importers of a repo
            │      (via importers call)
            ├─── it is possible to read an individual importer of a repo
            │      (via importer call)
            ├─── It is possible to update a distributor on a repo.
            │    └─── it is possible to read the updated distributor
            └─── It is possible to delete a distributor from a repo.

.. _repository:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/index.html

"""
from __future__ import unicode_literals
import copy

import requests

from pulp_smash.config import get_config
from pulp_smash.constants import REPOSITORY_PATH, ERROR_KEYS
from pulp_smash.utils import uuid4
from unittest2 import TestCase, skip

from sys import version_info
if version_info.major == 2:
    from urllib import urlencode  # pylint:disable=no-name-in-module
else:
    from urllib.parse import urlencode  # noqa pylint:disable=no-name-in-module,import-error

# pylint:disable=duplicate-code
# Once https://github.com/PulpQE/pulp-smash/pull/28#discussion_r44172668
# is resolved, pylint can be re-enabled.

ISO_DISTRIBUTOR = {
    'distributor_id': 'iso_distributor',
    'distributor_type_id': 'iso_distributor',
    'distributor_config': {},
    'auto_publish': True
}

SERIALIZED_ISO_DISTRIBUTOR = {
    '_href': '/pulp/api/v2/repositories/{repo}/distributors/iso_distributor/',
    'auto_publish': True,
    'config': {},
    'id': 'iso_distributor',
    'distributor_type_id': 'iso_distributor',
    'last_publish': None,
}

ISO_IMPORTER_TYPE_ID = 'iso_importer'

SERIALIZED_ISO_IMPORTER = {
    'id': 'iso_importer',
    'importer_type_id': 'iso_importer',
    '_href': '/pulp/api/v2/repositories/{repo}/importers/iso_importer/'
}


class RepoBaseTest(TestCase):

    @classmethod
    def get(cls, path, query=None):
        """Build a url and make a get request."""
        if isinstance(query, dict):
            query = urlencode(query)
        if query is not None:
            full_url = "{base}{path}?{query}".format(base=cls.cfg.base_url,
                                                     path=path, query=query)
        else:
            full_url = "{base}{path}".format(base=cls.cfg.base_url, path=path)
        return requests.get(full_url, **cls.cfg.get_requests_kwargs())

    def _build_expected(self, expected_template, repo_id):
        expected = copy.deepcopy(expected_template)
        expected['_href'] = expected['_href'].format(repo=repo_id)
        return expected


class CreateSuccessTestCase(TestCase):
    """Establish that we can create repositories."""

    @classmethod
    def setUpClass(cls):
        """Create several repositories.

        Create one repository with the minimum required attributes, and a
        second with all available attributes except importers and distributors.

        """
        cls.cfg = get_config()
        cls.url = cls.cfg.base_url + REPOSITORY_PATH
        cls.bodies = (
            {'id': uuid4()},
            {
                'id': uuid4(),
                'display_name': uuid4(),
                'description': uuid4(),
                'notes': {uuid4(): uuid4()},
            },

        )
        cls.responses = tuple((
            requests.post(
                cls.url,
                json=body,
                **cls.cfg.get_requests_kwargs()
            )
            for body in cls.bodies
        ))

    def test_status_code(self):
        """Assert that each response has a HTTP 201 status code."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertEqual(response.status_code, 201)

    def test_location_header(self):
        """Assert that the Location header is correctly set in the response."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertEqual(
                    self.url + self.bodies[i]['id'] + '/',
                    response.headers['Location']
                )

    def test_attributes(self):
        """Assert that each repository has the requested attributes."""
        for i, body in enumerate(self.bodies):
            with self.subTest(body):
                attributes = self.responses[i].json()
                self.assertLessEqual(set(body.keys()), set(attributes.keys()))
                attributes = {key: attributes[key] for key in body.keys()}
                self.assertEqual(body, attributes)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repositories."""
        for response in cls.responses:
            requests.delete(
                cls.cfg.base_url + response.json()['_href'],
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()


class CreateFailureTestCase(TestCase):
    """Establish that repositories are not created in documented scenarios."""

    @classmethod
    def setUpClass(cls):
        """Create several repositories.

        Each repository is created to test a different failure scenario. The
        first repository is created in order to test duplicate ids.

        """
        cls.cfg = get_config()
        cls.url = cls.cfg.base_url + REPOSITORY_PATH
        identical_id = uuid4()
        cls.bodies = (
            (201, {'id': identical_id}),
            (400, {'id': None}),
            (400, ['Incorrect data type']),
            (400, {'missing_required_keys': 'id'}),
            (409, {'id': identical_id}),
        )
        cls.responses = tuple((
            requests.post(
                cls.url,
                json=body[1],
                **cls.cfg.get_requests_kwargs()
            )
            for body in cls.bodies
        ))

    def test_status_code(self):
        """Assert that each response has the expected HTTP status code."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertEqual(response.status_code, self.bodies[i][0])

    def test_location_header(self):
        """Assert that the Location header is correctly set in the response."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                if self.bodies[i][0] == 201:
                    self.assertEqual(
                        self.url + self.bodies[i][1]['id'] + '/',
                        response.headers['Location']
                    )
                else:
                    self.assertNotIn('Location', response.headers)

    def test_exception_keys_json(self):
        """Assert the JSON body returned contains the correct keys."""
        for i, response in enumerate(self.responses):
            if self.bodies[i][0] >= 400:
                response_body = response.json()
                with self.subTest(self.bodies[i]):
                    for error_key in ERROR_KEYS:
                        with self.subTest(error_key):
                            self.assertIn(error_key, response_body)

    def test_exception_json_http_status(self):
        """Assert the JSON body returned contains the correct HTTP code."""
        for i, response in enumerate(self.responses):
            if self.bodies[i][0] >= 400:
                with self.subTest(self.bodies[i]):
                    json_status = response.json()['http_status']
                    self.assertEqual(json_status, self.bodies[i][0])

    @classmethod
    def tearDownClass(cls):
        """Delete the created repositories."""
        for response in cls.responses:
            if response.status_code == 201:
                requests.delete(
                    cls.cfg.base_url + response.json()['_href'],
                    **cls.cfg.get_requests_kwargs()
                ).raise_for_status()


class ReadUpdateDeleteSuccessTestCase(RepoBaseTest):
    """Establish that we can read, update, and delete repositories.

    This test assumes that the assertions in :class:`CreateSuccessTestCase` are
    valid.

    """

    @classmethod
    def setUpClass(cls):
        """Create three repositories to read, update, and delete."""
        cls.cfg = get_config()
        cls.update_body = {
            'delta': {
                'display_name': uuid4(),
                'description': uuid4()
            }
        }
        cls.bodies = [{'id': uuid4()} for _ in range(3)]
        cls.paths = []
        for body in cls.bodies:
            response = requests.post(
                cls.cfg.base_url + REPOSITORY_PATH,
                json=body,
                **cls.cfg.get_requests_kwargs()
            )
            response.raise_for_status()
            cls.paths.append(response.json()['_href'])

        # Read, update, and delete the three repositories, respectively.
        cls.read_response = cls.get(cls.paths[0])
        cls.distributors_response = cls.get(
            cls.paths[0], query="distributors=true")
        cls.importers_response = cls.get(cls.paths[0], query="importers=true")
        cls.details_response = cls.get(cls.paths[0], query="details=true")
        cls.update_response = requests.put(
            cls.cfg.base_url + cls.paths[1],
            json=cls.update_body,
            **cls.cfg.get_requests_kwargs()
        )
        cls.delete_response = requests.delete(
            cls.cfg.base_url + cls.paths[2],
            **cls.cfg.get_requests_kwargs()
        )

    def test_status_code(self):
        """Assert that each response has a 200 status code."""
        expected_status_codes = [
            ('read_response', 200), ('update_response', 200),
            ('delete_response', 202), ('distributors_response', 200),
            ('importers_response', 200), ('details_response', 200)
        ]
        for attr, expected_status in expected_status_codes:
            with self.subTest(attr):
                self.assertEqual(
                    getattr(self, attr).status_code,
                    expected_status
                )

    def test_read_attributes(self):
        """Assert that the read repository has the correct attributes."""
        attributes = self.read_response.json()
        self.assertLessEqual(
            set(self.bodies[0].keys()),
            set(attributes.keys())
        )
        attributes = {key: attributes[key] for key in self.bodies[0].keys()}
        self.assertEqual(self.bodies[0], attributes)

    def test_distributors_response(self):
        """Assert that the read with distributors has correct attributes."""
        repo_with_distributors = self.distributors_response.json()
        self.assertTrue('distributors' in repo_with_distributors)
        self.assertEqual(repo_with_distributors['distributors'], [])

    def test_importers_response(self):
        """Assert that the read with importers has the correct attributes."""
        repo_with_importers = self.importers_response.json()
        self.assertTrue('importers' in repo_with_importers)
        self.assertEqual(repo_with_importers['importers'], [])

    def test_details_response(self):
        repo_with_details = self.details_response.json()
        self.assertTrue('distributors' in repo_with_details)
        self.assertTrue('importers' in repo_with_details)
        self.assertEqual(repo_with_details['distributors'], [])
        self.assertEqual(repo_with_details['importers'], [])

    def test_update_attributes_spawned_tasks(self):  # noqa pylint:disable=invalid-name
        """Assert that `spawned_tasks` is present and no tasks were created."""
        response = self.update_response.json()
        self.assertIn('spawned_tasks', response)
        self.assertListEqual([], response['spawned_tasks'])

    def test_update_attributes_result(self):
        """Assert that `result` is present and has the correct attributes."""
        response = self.update_response.json()
        self.assertIn('result', response)
        for key, value in self.update_body['delta'].items():
            with self.subTest(key):
                self.assertIn(key, response['result'])
                self.assertEqual(value, response['result'][key])

    @classmethod
    def tearDownClass(cls):
        """Delete the created repositories."""
        for path in cls.paths[:2]:
            requests.delete(
                cls.cfg.base_url + path,
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()


class CreateISORepoSuccessCase(TestCase):
    """
    Establish that we can create typed repositories, complete with importers
    and distributors. In this case, we use the ISO plugin for simplicity.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create several iso repositories.

        Create a repository with all available attributes including a basic
        configuration for the iso importer and iso distributors.
        """
        cls.cfg = get_config()
        cls.url = cls.cfg.base_url + REPOSITORY_PATH
        cls.bodies = (
            {
                'id': uuid4(),
                'display_name': uuid4(),
                'description': uuid4(),
                'notes': {uuid4(): uuid4()},
                'distributors': [ISO_DISTRIBUTOR],
                'importer_type_id': ISO_IMPORTER_TYPE_ID,
                'importer_config': {},
            },

        )
        cls.responses = tuple((
            requests.post(
                cls.url,
                json=body,
                **cls.cfg.get_requests_kwargs()
            )
            for body in cls.bodies
        ))

    def test_status_code(self):
        """Assert that each response has a HTTP 201 status code."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertEqual(response.status_code, 201)

    def test_location_header(self):
        """Assert that the Location header is correctly set in the response."""
        for i, response in enumerate(self.responses):
            with self.subTest(self.bodies[i]):
                self.assertEqual(
                    self.url + self.bodies[i]['id'] + '/',
                    response.headers['Location']
                )

    def test_attributes(self):
        """Assert that each repository has the requested attributes."""
        for i, body in enumerate(self.bodies):
            with self.subTest(body):
                attributes = self.responses[i].json()
                excluded_keys = set(
                    ['distributors', 'importer_type_id', 'importer_config'])
                expected_body = {key: body[key]
                                 for key in set(body.keys()) - excluded_keys}
                self.assertLessEqual(
                    expected_body.keys(), set(attributes.keys()))
                attributes = {key: attributes[key]
                              for key in expected_body.keys()}
                self.assertDictEqual(expected_body, attributes)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repositories."""
        for response in cls.responses:
            requests.delete(
                cls.cfg.base_url + response.json()['_href'],
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()


class ReadUpdateDeleteISORepo(RepoBaseTest):
    """Establish that we can interact with typed repositories as expected."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = get_config()
        cls.bodies = [{
            'id': uuid4(),
            'notes': {'this': 'one'},
            'distributors': [ISO_DISTRIBUTOR],
            'importer_type_id': ISO_IMPORTER_TYPE_ID,
            'importer_config': {},
        }, {
            'id': uuid4(),
            'display_name': uuid4(),
            'description': uuid4(),
            'distributors': [ISO_DISTRIBUTOR],
            'importer_type_id': ISO_IMPORTER_TYPE_ID,
            'importer_config': {},
        }, {
            'id': uuid4(),
            'display_name': uuid4(),
            'description': uuid4(),
            'notes': {uuid4(): uuid4()},
            'distributors': [ISO_DISTRIBUTOR],
            'importer_type_id': ISO_IMPORTER_TYPE_ID,
            'importer_config': {},
        }]
        cls.update_body = {
            'delta': {
                'display_name': uuid4(),
                'description': uuid4()
            }
        }
        cls.paths = []

        for body in cls.bodies:
            response = requests.post(
                cls.cfg.base_url + REPOSITORY_PATH,
                json=body,
                **cls.cfg.get_requests_kwargs()
            )
            response.raise_for_status()
            cls.paths.append(response.json()['_href'])

        # All 3 options for reads
        cls.read_response = cls.get(cls.paths[0])
        cls.distributors_response = cls.get(
            cls.paths[0], query="distributors=true")
        cls.importers_response = cls.get(cls.paths[0], query="importers=true")
        cls.details_response = cls.get(cls.paths[0], query="details=true")

        # Update and delete
        cls.update_response = requests.put(
            cls.cfg.base_url + cls.paths[1],
            json=cls.update_body,
            **cls.cfg.get_requests_kwargs()
        )
        cls.delete_response = requests.delete(
            cls.cfg.base_url + cls.paths[2],
            **cls.cfg.get_requests_kwargs()
        )

    def test_status_code(self):
        """Assert that each response has a 200 status code."""
        expected_status_codes = [
            ('read_response', 200), ('distributors_response', 200),
            ('importers_response', 200), ('details_response', 200),
            ('update_response', 200), ('delete_response', 202),
        ]
        for attr, expected_status in expected_status_codes:
            with self.subTest(attr):
                self.assertEqual(
                    getattr(self, attr).status_code,
                    expected_status
                )

    def test_read_attributes(self):
        """Assert that the read repository has the correct attributes."""
        read_request = self.bodies[0]
        attributes = self.read_response.json()
        excluded_keys = set(
            ['distributors', 'importer_type_id', 'importer_config'])
        expected_body = {key: read_request[key]
                         for key in set(read_request.keys()) - excluded_keys}
        self.assertLessEqual(expected_body.keys(), set(attributes.keys()))
        attributes = {key: attributes[key] for key in expected_body.keys()}
        self.assertDictEqual(expected_body, attributes)

    def test_distributors_response(self):
        """Assert that the read with distributors has correct attributes."""
        repo_with_distributors = self.distributors_response.json()
        self.assertTrue('distributors' in repo_with_distributors)
        self.assertEqual(len(repo_with_distributors['distributors']), 1)

        expected_distributor = self._build_expected(
            SERIALIZED_ISO_DISTRIBUTOR, repo_with_distributors['id'])
        self.assertLessEqual(
            expected_distributor, repo_with_distributors['distributors'][0])

    def test_importers_response(self):
        """Assert that the read with importers has the correct attributes."""
        repo_with_importers = self.importers_response.json()
        self.assertTrue('importers' in repo_with_importers)
        self.assertEqual(len(repo_with_importers['importers']), 1)

        expected_importer = self._build_expected(SERIALIZED_ISO_IMPORTER,
                                                 repo_with_importers['id'])
        self.assertLessEqual(
            expected_importer, repo_with_importers['importers'][0])

    def test_details_response(self):
        """Assert that the read with details has the correct attributes."""
        repo_with_details = self.details_response.json()
        self.assertTrue('distributors' in repo_with_details)
        self.assertTrue('importers' in repo_with_details)

        expected_importer = self._build_expected(SERIALIZED_ISO_IMPORTER,
                                                 repo_with_details['id'])
        self.assertLessEqual(
            expected_importer, repo_with_details['importers'][0])

        expected_distributor = self._build_expected(SERIALIZED_ISO_DISTRIBUTOR,
                                                    repo_with_details['id'])
        self.assertLessEqual(
            expected_distributor, repo_with_details['distributors'][0])

    def test_update_attributes_spawned_tasks(self):  # noqa pylint:disable=invalid-name
        """Assert that `spawned_tasks` is present and no tasks were created."""
        response = self.update_response.json()
        self.assertIn('spawned_tasks', response)
        self.assertListEqual([], response['spawned_tasks'])

    def test_update_attributes_result(self):
        """Assert that `result` is present and has the correct attributes."""
        response = self.update_response.json()
        self.assertIn('result', response)
        for key, value in self.update_body['delta'].items():
            with self.subTest(key):
                self.assertIn(key, response['result'])
                self.assertEqual(value, response['result'][key])

    @classmethod
    def tearDownClass(cls):
        """Delete the created repositories."""
        for path in cls.paths[:2]:
            requests.delete(
                cls.cfg.base_url + path,
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()


class ISOImporterDistributorCreateSuccess(RepoBaseTest):
    """Establish that we can add importers and distributors to repositories."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = get_config()

        # Create 3 repositories
        cls.repo_create_bodies = [{'id': uuid4()} for _ in range(3)]
        cls.repo_paths = []
        # cls.repo_create_responses = []
        for body in cls.repo_create_bodies:
            response = requests.post(
                cls.cfg.base_url + REPOSITORY_PATH,
                json=body,
                **cls.cfg.get_requests_kwargs()
            )
            response.raise_for_status()
            cls.repo_paths.append(response.json()['_href'])
            # cls.repo_create_responses.append(response)

        # Add a distrtibutor to each repo
        cls.dist_create_responses = []
        cls.dist_paths = []
        cls.dist_ids = []
        for path in cls.repo_paths:
            dist_id = uuid4()
            distributor_create_body = {
                'distributor_type_id': ISO_DISTRIBUTOR['distributor_type_id'],
                'distributor_config': {},
                'distributor_id': dist_id
            }
            cls.dist_ids.append(dist_id)
            response = requests.post(
                cls.cfg.base_url + path + "distributors/",
                json=distributor_create_body,
                **cls.cfg.get_requests_kwargs()
            )
            response.raise_for_status()
            cls.dist_paths.append(response.json()['_href'])
            cls.dist_create_responses.append(response)

        # Add an importer to each repo
        cls.imp_create_responses = []
        cls.imp_paths = []
        for path in cls.repo_paths:
            importer_create_body = {'importer_type_id': ISO_IMPORTER_TYPE_ID}
            repo_importers_path = path + "importers/"
            response = requests.post(
                "{base}{path}".format(base=cls.cfg.base_url,
                                      path=repo_importers_path),
                json=importer_create_body,
                **cls.cfg.get_requests_kwargs()
            )
            response.raise_for_status()
            cls.imp_create_responses.append(response)
            cls.imp_paths.append(repo_importers_path)

        cls.dist_update_body = {
            'delta': {'auto_publish': True},
            'distributor_config': {'relative_url': 'updated/url'}
        }
        cls.dist_update_response = requests.put(
            cls.cfg.base_url + cls.dist_paths[1],
            json=cls.dist_update_body,
            **cls.cfg.get_requests_kwargs()
        )
        cls.delete_path = cls.cfg.base_url + cls.dist_paths[2]
        cls.dist_delete_response = requests.delete(
            cls.delete_path,
            **cls.cfg.get_requests_kwargs()
        )

        iso_distributors_path = '{base}distributors/'.format(
            base=cls.repo_paths[0])
        iso_imp_path = '{base}importers/'.format(base=cls.repo_paths[0])

        # Perform reads on the created objects
        cls.read_response = cls.get(cls.repo_paths[0])
        cls.repo_distributors_response = cls.get(cls.repo_paths[0],
                                                 query="distributors=true")
        cls.repo_importers_response = cls.get(cls.repo_paths[0],
                                              query="importers=true")
        cls.details_response = cls.get(cls.repo_paths[0], query="details=true")
        cls.all_dists = cls.get(iso_distributors_path)
        cls.one_distributor = cls.get(cls.dist_paths[0])
        cls.all_importers = cls.get(iso_imp_path)
        cls.one_importer = cls.get(cls.imp_paths[0])
        cls.get_updated_distributor = cls.get(cls.dist_paths[1])

        cls.deleted_http_actions = ('get', 'delete')
        cls.deleted_responses = tuple((
            getattr(requests, http_action)(
                cls.delete_path,
                **cls.cfg.get_requests_kwargs()
            )
            for http_action in cls.deleted_http_actions
        ))

    def test_status_code(self):
        """Assert that each response has a 200 status code."""

        for response in self.dist_create_responses:
            with self.subTest(response):
                self.assertEqual(response.status_code, 201)
        expected_status_codes = [
            ('dist_update_response', 202), ('read_response', 200),
            ('repo_distributors_response', 200),
            ('repo_importers_response', 200), ('details_response', 200),
            ('all_dists', 200),  ('one_distributor', 200),
            ('all_importers', 200), ('one_importer', 200),
            ('dist_delete_response', 202), ('get_updated_distributor', 200)
        ]
        for attr, expected_status in expected_status_codes:
            with self.subTest(attr):
                self.assertEqual(
                    getattr(self, attr).status_code,
                    expected_status
                )

    def test_read_attributes(self):
        """Assert that the read repository has the correct attributes."""
        read_request = self.repo_create_bodies[0]
        attributes = self.read_response.json()
        excluded_keys = set(
            ['distributors', 'importer_type_id', 'importer_config'])
        expected_body = {key: read_request[key]
                         for key in set(read_request.keys()) - excluded_keys}
        self.assertLessEqual(expected_body.keys(), set(attributes.keys()))
        attributes = {key: attributes[key] for key in expected_body.keys()}
        self.assertDictEqual(expected_body, attributes)

    def test_repo_distributors_response(self):
        """Assert that read repos with distributors has correct attributes."""
        repo_with_distributors = self.repo_distributors_response.json()
        self.assertTrue('distributors' in repo_with_distributors)
        self.assertEqual(len(repo_with_distributors['distributors']), 1)

        expected_distributor = self._build_expected(
            SERIALIZED_ISO_DISTRIBUTOR, repo_with_distributors['id'])
        self.assertLessEqual(
            expected_distributor, repo_with_distributors['distributors'][0])

    def test_all_distributors_response(self):
        """Assert that read distributors has the correct attributes."""
        all_distributors = self.all_dists.json()
        self.assertEqual(len(all_distributors), 1)
        one_distributor = all_distributors[0]

        expected_distributor = self._build_expected(SERIALIZED_ISO_DISTRIBUTOR,
                                                    one_distributor)
        self.assertLessEqual(expected_distributor, one_distributor)

    def test_one_distributor_response(self):
        """Assert that read one distributor has the correct attributes."""
        one_distributor = self.one_distributor.json()

        expected_distributor = self._build_expected(SERIALIZED_ISO_DISTRIBUTOR,
                                                    one_distributor)
        self.assertLessEqual(expected_distributor, one_distributor)

    def test_updated_distributor_response(self):
        """Assert that update distributor response has correct attributes."""
        one_distributor = self.get_updated_distributor.json()
        expected_auto_publish = self.dist_update_body['delta']['auto_publish']
        expected_rel_url = \
            self.dist_update_body['distributor_config']['relative_url']
        self.assertTrue(
            one_distributor['auto_publish'] is expected_auto_publish)
        self.assertEqual(
            one_distributor['config']['relative_url'], expected_rel_url)

    def test_repo_importers_response(self):
        """Assert that the read with importers has the correct attributes."""
        repo_with_importers = self.repo_importers_response.json()
        self.assertTrue('importers' in repo_with_importers)
        self.assertEqual(len(repo_with_importers['importers']), 1)

        expected_importer = self._build_expected(SERIALIZED_ISO_IMPORTER,
                                                 repo_with_importers['id'])
        self.assertLessEqual(
            expected_importer, repo_with_importers['importers'][0])

    def test_importers_response(self):
        """Assert that read importers has the correct attributes."""
        all_importers = self.all_importers.json()
        self.assertEqual(len(all_importers), 1)
        one_importer = all_importers[0]

        expected_importer = self._build_expected(SERIALIZED_ISO_IMPORTER,
                                                 one_importer)
        self.assertLessEqual(expected_importer, one_importer)

    def test_one_importer_response(self):
        """Assert that read one imoporter has the correct attributes."""
        one_importer = self.one_importer.json()

        expected_importer = self._build_expected(SERIALIZED_ISO_IMPORTER,
                                                 one_importer)
        self.assertLessEqual(expected_importer, one_importer)

    def test_details_response(self):
        """Assert that repo with details has importers and distributors."""
        repo_with_details = self.details_response.json()
        self.assertTrue('distributors' in repo_with_details)
        self.assertTrue('importers' in repo_with_details)

        expected_importer = self._build_expected(SERIALIZED_ISO_IMPORTER,
                                                 repo_with_details['id'])
        self.assertLessEqual(
            expected_importer, repo_with_details['importers'][0])

        expected_distributor = self._build_expected(SERIALIZED_ISO_DISTRIBUTOR,
                                                    repo_with_details['id'])
        self.assertLessEqual(
            expected_distributor, repo_with_details['distributors'][0])

    def test_cannot_get_deleted_distributor(self):
        """Assert that deleted distributors cannot be read or updated."""
        for i, response in enumerate(self.deleted_responses):
            with self.subTest(self.deleted_http_actions[i]):
                self.assertEqual(response.status_code, 404)

    @classmethod
    def tearDownClass(cls):
        """Delete the created repositories and associated distributors."""
        for path in cls.repo_paths:
            requests.delete(
                cls.cfg.base_url + path,
                **cls.cfg.get_requests_kwargs()
            ).raise_for_status()
