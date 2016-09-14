# coding=utf-8
"""Test the API's `content applicability` functionality.

When a user asks Pulp to regenerate content applicability, Pulp responds with a
call report and starts executing tasks in series. Starting with Pulp 2.8, it is
possible for a user to explicitly request that Pulp execute tasks in parallel
instead. This functionality is only available for certain API calls, and when
this is done, Pulp returns a group call report instead of a regular call
report.  (See :data:`pulp_smash.constants.CALL_REPORT_KEYS` and
:data:`pulp_smash.constants.GROUP_CALL_REPORT_KEYS`.) :class:`SeriesTestCase`
and :class:`ParallelTestCase` test these two use cases, respectively.

.. _content applicability:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/applicability.html
"""
import inspect
import unittest

from packaging.version import Version

from pulp_smash import api, config
from pulp_smash.constants import CALL_REPORT_KEYS, GROUP_CALL_REPORT_KEYS

_PATHS = {
    'consumer': '/pulp/api/v2/consumers/actions/content/regenerate_applicability/',  # noqa
    'repo': '/pulp/api/v2/repositories/actions/content/regenerate_applicability/',  # noqa
}


class _SuccessTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an empty set of responses."""
        if inspect.getmro(cls)[0] == _SuccessTestCase:
            raise unittest.SkipTest('Abstract base class.')
        cls.cfg = config.get_config()
        cls.responses = {}

    def test_status_code(self):
        """Assert each response has an HTTP 202 status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 202)


class SeriesTestCase(_SuccessTestCase):
    """Ask Pulp to regenerate content applicability for consumers and repos.

    Do so in series. See
    :mod:`pulp_smash.tests.platform.api_v2.test_content_applicability`.
    """

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        super(SeriesTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.echo_handler)
        for key, path in _PATHS.items():
            cls.responses[key] = client.post(path, {key + '_criteria': {}})

    def test_body(self):
        """Assert each response is JSON and has a correct structure."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                response_keys = frozenset(response.json().keys())
                self.assertEqual(response_keys, CALL_REPORT_KEYS)


class ParallelTestCase(_SuccessTestCase):
    """Ask Pulp to regenerate content applicability for consumers and repos.

    Do so in parallel. See
    :mod:`pulp_smash.tests.platform.api_v2.test_content_applicability`.
    """

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        super(ParallelTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.echo_handler)
        for key in {'repo'}:
            json = {key + '_criteria': {}, 'parallel': True}
            cls.responses[key] = client.post(_PATHS[key], json)

    def setUp(self):
        """Ensure this test only runs on Pulp 2.8 and later."""
        min_ver = '2.8'
        ver = self.cfg.version
        if ver < Version(min_ver):
            self.skipTest(
                'This test requires Pulp {} or later, but Pulp {} is being '
                'tested.'.format(min_ver, ver)
            )

    def test_body(self):
        """Assert each response is JSON and has a correct structure."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                response_keys = frozenset(response.json().keys())
                self.assertEqual(response_keys, GROUP_CALL_REPORT_KEYS)


class FailureTestCase(unittest.TestCase):
    """Fail to generate content applicability for consumers and repos."""

    @classmethod
    def setUpClass(cls):
        """Make calls to the server and save the responses."""
        client = api.Client(config.get_config(), api.echo_handler)
        cls.responses = {
            key: client.post(path, {key + '_criteriaa': {}})
            for key, path in _PATHS.items()
        }

    def test_status_code(self):
        """Assert each response has an HTTP 400 status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, 400)

    def test_body(self):
        """Assert each response is JSON and doesn't look like a call report."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                response_keys = frozenset(response.json().keys())
                self.assertNotEqual(response_keys, CALL_REPORT_KEYS)
