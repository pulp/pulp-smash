# coding=utf-8
"""Unit tests for :mod:`pulp_smash.selectors`."""
from __future__ import unicode_literals

import random

import mock
from unittest2 import TestCase

from pulp_smash import selectors


class BugTestableTestCase(TestCase):
    """Test :meth:`pulp_smash.selectors.bug_is_testable` and its partner."""

    def test_testable_status(self):
        """Make the dependent function return a "testable" bug status."""
        with mock.patch.object(
            selectors,
            '_get_bug_status',
            # pylint:disable=protected-access
            return_value=random.sample(selectors._TESTABLE_BUGS, 1)[0]
        ):
            with self.subTest():
                self.assertTrue(selectors.bug_is_testable(None))
            with self.subTest():
                self.assertFalse(selectors.bug_is_untestable(None))

    def test_untestable_status(self):
        """Make the dependent function return a "untestable" bug status."""
        with mock.patch.object(
            selectors,
            '_get_bug_status',
            # pylint:disable=protected-access
            return_value=random.sample(selectors._UNTESTABLE_BUGS, 1)[0]
        ):
            with self.subTest():
                self.assertFalse(selectors.bug_is_testable(None))
            with self.subTest():
                self.assertTrue(selectors.bug_is_untestable(None))

    def test_unknown_status(self):
        """Make the dependent function return an unknown bug status."""
        with mock.patch.object(
            selectors,
            '_get_bug_status',
            return_value=None,
        ):
            with self.assertRaises(selectors.BugStatusUnknownError):
                selectors.bug_is_testable(None)
