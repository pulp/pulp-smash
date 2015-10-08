# coding=utf-8
"""Test the API's `content applicability` functionality.

.. _content applicability:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/consumer/applicability.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from unittest2 import TestCase

CALL_REPORT_KEYS = {'error', 'result', 'spawned_tasks'}
CONSUMER = '/pulp/api/v2/consumers/actions/content/regenerate_applicability/'
REPO = '/pulp/api/v2/repositories/actions/content/regenerate_applicability/'


class SuccessTestCase(TestCase):
    """Generate content applicability for updated consumers and repos."""

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        config = get_config()
        base_url = config.pop('base_url')
        path_json_pairs = (
            (CONSUMER, {'consumer_criteria': {}}),
            (REPO, {'repo_criteria': {}})
        )
        cls.responses = tuple((
            requests.post(base_url + path, json=json, **config)
            for path, json in path_json_pairs
        ))

    def test_status_code(self):
        """Assert that the responses have HTTP 202 status codes."""
        for i, response in enumerate(self.responses):
            with self.subTest(i):
                self.assertEqual(response.status_code, 202)

    def test_body(self):
        """Assert that the responses are JSON and appear to be call reports."""
        for i, response in enumerate(self.responses):
            with self.subTest(i):
                self.assertEqual(set(response.json().keys()), CALL_REPORT_KEYS)


class FailureTestCase(TestCase):
    """Unsuccessfully generate content applicability for consumers and
    repos.

    """

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        config = get_config()
        base_url = config.pop('base_url')
        path_json_pairs = (
            (CONSUMER, {'consumer_criteriaa': {}}),
            (REPO, {'repo_criteriaa': {}})
        )
        cls.responses = tuple((
            requests.post(base_url + path, json=json, **config)
            for path, json in path_json_pairs
        ))

    def test_status_code(self):
        """Assert that each response has an HTTP 400 status code."""
        for i, response in enumerate(self.responses):
            with self.subTest(i):
                self.assertEqual(response.status_code, 400)

    def test_body(self):
        """Assert that the responses are JSON and appear to be call reports."""
        for i, resp in enumerate(self.responses):
            with self.subTest(i):
                self.assertNotEqual(set(resp.json().keys()), CALL_REPORT_KEYS)
