# coding=utf-8
"""Test the `repository`_ API endpoints.

The assumptions explored in this module have the following dependencies::

        It is possible to create an untyped repository.
        ├── It is impossible to create a repository with a duplicate ID
        │   or other invalid attributes.
        ├── It is possible to read a repository, including its importers and
        │   distributors.
        ├── It is possible to update a repository.
        └── It is possible to delete a repository.

.. _repository:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/index.html
"""
from urllib.parse import urljoin, urlparse

from packaging.version import Version

from pulp_smash import api, utils
from pulp_smash.constants import REPOSITORY_PATH, ERROR_KEYS
from pulp_smash.selectors import bug_is_untestable, require


class CreateSuccessTestCase(utils.BaseAPITestCase):
    """Establish we can create repositories."""

    @classmethod
    def setUpClass(cls):
        """Create several repositories.

        Create one repository with the minimum required attributes, and a
        second with all available attributes except importers and distributors.
        """
        super(CreateSuccessTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.bodies = [{'id': utils.uuid4()}]
        cls.bodies.append({
            'description': utils.uuid4(),
            'display_name': utils.uuid4(),
            'id': utils.uuid4(),
            'notes': {utils.uuid4(): utils.uuid4()},
        })
        cls.responses = []
        for body in cls.bodies:
            response = client.post(REPOSITORY_PATH, body)
            cls.responses.append(response)
            cls.resources.add(response.json()['_href'])

    def test_status_code(self):
        """Assert each response has an HTTP 201 status code."""
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                self.assertEqual(response.status_code, 201)

    @require('2.7')  # https://pulp.plan.io/issues/695
    def test_location_header(self):
        """Assert the Location header is correctly set in each response.

        According to RFC 7231, the `HTTP Location`_ header may be either an
        absolute or relative URL. Thus, given this request:

        .. code-block:: http

            GET /index.html HTTP/1.1
            Host: www.example.com

        These two responses are equivalent:

        .. code-block:: http

            HTTP/1.1 302 FOUND
            Location: http://www.example.com/index.php

        .. code-block:: http

            HTTP/1.1 302 FOUND
            Location: /index.php

        This test abides by the RFC and allows Pulp to return either absolute
        or relative URLs.

        .. _HTTP Location: https://en.wikipedia.org/wiki/HTTP_location
        """
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                # >>> urlparse('http://example.com/index.php').path == \
                # ... urlparse('/index.php').path
                # True
                actual_path = urlparse(response.headers['Location']).path
                expect_path = urljoin(REPOSITORY_PATH, body['id'] + '/')
                self.assertEqual(actual_path, expect_path)

    def test_attributes(self):
        """Assert that each repository has the requested attributes."""
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                attrs = response.json()
                self.assertLessEqual(set(body.keys()), set(attrs.keys()))
                attrs = {key: attrs[key] for key in body.keys()}
                self.assertEqual(body, attrs)


class CreateFailureTestCase(utils.BaseAPITestCase):
    """Establish that repositories are not created in documented scenarios."""

    @classmethod
    def setUpClass(cls):
        """Create several repositories.

        Each repository is created to test a different failure scenario. The
        first repository is created in order to test duplicate ids.
        """
        super(CreateFailureTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, {'id': utils.uuid4()})
        cls.resources.add(repo['_href'])

        client.response_handler = api.echo_handler
        cls.bodies = (
            {'id': None},  # 400
            ['Incorrect data type'],  # 400
            {'missing_required_keys': 'id'},  # 400
            {'id': repo['id']},  # 409
        )
        cls.status_codes = (400, 400, 400, 409)
        cls.responses = [
            client.post(REPOSITORY_PATH, body) for body in cls.bodies
        ]

    def test_status_code(self):
        """Assert that each response has the expected HTTP status code."""
        for body, response, status_code in zip(
                self.bodies, self.responses, self.status_codes):
            if (body == ['Incorrect data type'] and
                    self.cfg.version < Version('2.8')):
                continue  # https://pulp.plan.io/issues/1356
            with self.subTest(body=body):
                self.assertEqual(response.status_code, status_code)

    def test_body_status_code(self):
        """Assert that each response body has the expected HTTP status code."""
        for body, response, status_code in zip(
                self.bodies, self.responses, self.status_codes):
            if (body == ['Incorrect data type'] and
                    self.cfg.version < Version('2.8')):
                continue  # https://pulp.plan.io/issues/1356
            with self.subTest(body=body):
                self.assertEqual(response.json()['http_status'], status_code)

    def test_location_header(self):
        """Assert that the Location header is correctly set in the response."""
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                self.assertNotIn('Location', response.headers)

    def test_exception_keys_json(self):
        """Assert the JSON body returned contains the correct keys."""
        for body, response in zip(self.bodies, self.responses):
            with self.subTest(body=body):
                if bug_is_untestable(1413, self.cfg.version):
                    self.skipTest('https://pulp.plan.io/issues/1413')
                response_keys = frozenset(response.json().keys())
                self.assertEqual(response_keys, ERROR_KEYS)


class ReadUpdateDeleteTestCase(utils.BaseAPITestCase):
    """Establish we can read, update and delete repositories.

    This test case assumes the assertions in :class:`CreateSuccessTestCase`
    hold true.
    """

    @classmethod
    def setUpClass(cls):
        """Create three repositories and read, update and delete them."""
        super(ReadUpdateDeleteTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        cls.repos = tuple((
            client.post(REPOSITORY_PATH, {'id': utils.uuid4()})
            for _ in range(3)
        ))
        cls.responses = {}
        client.response_handler = api.safe_handler

        # Read the first repo
        path = cls.repos[0]['_href']
        cls.responses['read'] = client.get(path)
        for key in {'importers', 'distributors', 'details'}:
            cls.responses['read_' + key] = client.get(path, params={key: True})

        # Update the second repo
        path = cls.repos[1]['_href']
        cls.update_body = {'delta': {
            key: utils.uuid4() for key in {'description', 'display_name'}
        }}
        cls.responses['update'] = client.put(path, cls.update_body)

        # Delete the third.
        cls.responses['delete'] = client.delete(cls.repos[2]['_href'])

    def test_status_code(self):
        """Assert each response has a correct HTTP status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                status_code = 202 if key == 'delete' else 200
                self.assertEqual(response.status_code, status_code)

    def test_read(self):
        """Assert the "read" response body contains the correct attributes."""
        attrs = self.responses['read'].json()
        self.assertLessEqual(set(self.repos[0].keys()), set(attrs.keys()))
        attrs = {key: attrs[key] for key in self.repos[0].keys()}
        self.assertEqual(self.repos[0], attrs)

    def test_read_imp_distrib(self):
        """Assert reading with importers/distributors returns correct attrs."""
        for key in ('importers', 'distributors'):
            with self.subTest(key=key):
                attrs = self.responses['read_' + key].json()
                self.assertIn(key, attrs)
                self.assertEqual(attrs[key], [])

    def test_read_details(self):
        """Assert the read with details has the correct attributes."""
        attrs = self.responses['read_details'].json()
        for key in ('importers', 'distributors'):
            with self.subTest(key=key):
                self.assertIn(key, attrs)
                self.assertEqual(attrs[key], [])

    def test_update_spawned_tasks(self):
        """Assert the "update" response body mentions no spawned tasks."""
        attrs = self.responses['update'].json()
        self.assertIn('spawned_tasks', attrs)
        self.assertEqual(attrs['spawned_tasks'], [])

    def test_update_attributes_result(self):
        """Assert the "update" response body has the correct attributes."""
        attrs = self.responses['update'].json()
        self.assertIn('result', attrs)
        for key, value in self.update_body['delta'].items():
            with self.subTest(key=key):
                self.assertIn(key, attrs['result'])
                self.assertEqual(value, attrs['result'][key])
