# coding=utf-8
"""Test the API's `content applicability` functionality.

.. _content applicability:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/consumer/applicability.html

"""
from __future__ import unicode_literals

import requests
from pulp_smash.config import get_config
from pulp_smash.constants import CALL_REPORT_KEYS
from unittest2 import TestCase

_CONSUMER = '/pulp/api/v2/consumers/actions/content/regenerate_applicability/'
_REPO = '/pulp/api/v2/repositories/actions/content/regenerate_applicability/'


class SuccessTestCase(TestCase):
    """Generate content applicability for updated consumers and repos."""

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        cfg = get_config()
        path_json_pairs = (
            (_CONSUMER, {'consumer_criteria': {}}),
            (_REPO, {'repo_criteria': {}})
        )
        cls.responses = tuple((
            requests.post(
                cfg.base_url + path,
                json=json,
                **cfg.get_requests_kwargs()
            )
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
                self.assertEqual(
                    frozenset(response.json().keys()),
                    CALL_REPORT_KEYS,
                )


class FailureTestCase(TestCase):
    """Fail to generate content applicability for consumers and repos."""

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        cfg = get_config()
        path_json_pairs = (
            (_CONSUMER, {'consumer_criteriaa': {}}),
            (_REPO, {'repo_criteriaa': {}})
        )
        cls.responses = tuple((
            requests.post(
                cfg.base_url + path,
                json=json,
                **cfg.get_requests_kwargs()
            )
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
                self.assertNotEqual(
                    frozenset(resp.json().keys()),
                    CALL_REPORT_KEYS,
                )
