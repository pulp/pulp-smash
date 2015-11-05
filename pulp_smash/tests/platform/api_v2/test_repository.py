# coding=utf-8
"""Test the `repository`_ API endpoints.

The assumptions explored in this module have the following dependencies::

        It is possible to create a repository.
        ├── It is impossible to create a repository with a duplicate ID
        │   or other invalid attributes.
        ├── It is possible to read a repository.
        ├── It is possible to update a repository.
        └── It is possible to delete a repository.

.. _repository:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/index.html

"""
from __future__ import unicode_literals

import requests

from pulp_smash.config import get_config
from pulp_smash.constants import REPOSITORY_PATH, ERROR_KEYS
from pulp_smash.utils import rand_str
from unittest2 import TestCase

# pylint:disable=duplicate-code
# Once https://github.com/PulpQE/pulp-smash/pull/28#discussion_r44172668
# is resolved, pylint can be re-enabled.


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
            {'id': rand_str()},
            {
                'id': rand_str(),
                'display_name': rand_str(),
                'description': rand_str(),
                'notes': {rand_str(): rand_str()},
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
        identical_id = rand_str()
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


class ReadUpdateDeleteSuccessTestCase(TestCase):
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
                'display_name': rand_str(),
                'description': rand_str()
            }
        }
        cls.bodies = [{'id': rand_str()} for _ in range(3)]
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
        cls.read_response = requests.get(
            cls.cfg.base_url + cls.paths[0],
            **cls.cfg.get_requests_kwargs()
        )
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
        expected_status_codes = zip(
            ('read_response', 'update_response', 'delete_response'),
            (200, 200, 202)
        )
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
