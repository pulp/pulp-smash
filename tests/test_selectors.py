# coding=utf-8
"""Unit tests for :mod:`pulp_smash.selectors`."""
import random
import unittest
from unittest import mock

import requests
from packaging.version import InvalidVersion, Version

from pulp_smash import exceptions, selectors, utils

# It makes sense for unit tests to access otherwise private data.
# pylint:disable=protected-access


class GetTPRTestCase(unittest.TestCase):
    """Test method ``_get_tpr``."""

    def test_success(self):
        """Assert the method returns the target platform release if present."""
        version_str = utils.uuid4()
        bug_json = {'issue': {'custom_fields': [
            {'id': 1, 'value': 'foo'},
            {'id': 4, 'value': version_str},
            {'id': 9, 'value': 'bar'},
        ]}}
        random.shuffle(bug_json['issue']['custom_fields'])
        self.assertEqual(selectors._get_tpr(bug_json), version_str)

    def test_failure(self):
        """Assert the method raises the correct exception no TPR is present."""
        bug_json = {'issue': {
            'custom_fields': [
                {'id': 1, 'value': 'foo'},
                {'id': 3, 'value': 'bar'},
                {'id': 9, 'value': 'biz'},
            ],
            'id': 1234,
        }}
        with self.assertRaises(exceptions.BugTPRMissingError):
            selectors._get_tpr(bug_json)


class ConvertTPRTestCase(unittest.TestCase):
    """Test method ``_convert_tpr``."""

    def test_valid_version_string(self):
        """Assert ``version_string`` is converted if it is valid."""
        for version_str in ('0', '0.1', '0.1.2', '0.1.2.3', '1!0'):
            with self.subTest(version_str=version_str):
                version = Version(version_str)
                self.assertEqual(selectors._convert_tpr(version_str), version)

    def test_empty_version_string(self):
        """Assert ``version_string`` is converted if it is an empty string."""
        self.assertEqual(selectors._convert_tpr(''), Version('0'))

    def test_invalid_version_string(self):
        """Assert an exception is raised if ``version_string`` is invalid."""
        with self.assertRaises(InvalidVersion):
            selectors._convert_tpr('foo')


class GetBugTestCase(unittest.TestCase):
    """Test method ``_get_bug``."""

    def test_invalid_bug_id(self):
        """Assert an exception is raised if ``bug_id`` isn't an integer."""
        with self.assertRaises(TypeError):
            selectors._get_bug('1')


class BugIsTestableTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.selectors.bug_is_testable` and its partner."""

    def test_testable_status(self):
        """Assert the method correctly handles "testable" bug statuses."""
        ver = Version('0')
        for bug_status in selectors._TESTABLE_BUGS:
            bug = selectors._Bug(bug_status, ver)
            with mock.patch.object(selectors, '_get_bug', return_value=bug):
                with self.subTest(bug_status=bug_status):
                    self.assertTrue(selectors.bug_is_testable(None, ver))
                    self.assertFalse(selectors.bug_is_untestable(None, ver))

    def test_untestable_status(self):
        """Assert the method correctly handles "untestable" bug statuses."""
        ver = Version('0')
        for bug_status in selectors._UNTESTABLE_BUGS:
            bug = selectors._Bug(bug_status, ver)
            with mock.patch.object(selectors, '_get_bug', return_value=bug):
                with self.subTest(bug_status=bug_status):
                    self.assertFalse(selectors.bug_is_testable(None, ver))
                    self.assertTrue(selectors.bug_is_untestable(None, ver))

    def test_unknown_status(self):
        """Assert the method correctly handles an unknown bug status."""
        ver = Version('0')
        bug = selectors._Bug('foo', ver)
        with mock.patch.object(selectors, '_get_bug', return_value=bug):
            with self.assertRaises(exceptions.BugStatusUnknownError):
                selectors.bug_is_testable(None, ver)

    def test_connection_error(self):
        """Make the dependent function raise a connection error."""
        ver = Version('0')
        with mock.patch.object(selectors, '_get_bug') as get_bug:
            get_bug.side_effect = requests.exceptions.ConnectionError
            with self.assertWarns(RuntimeWarning):
                selectors.bug_is_testable(None, ver)
            with self.assertWarns(RuntimeWarning):
                selectors.bug_is_untestable(None, ver)
