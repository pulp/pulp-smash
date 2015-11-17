# coding=utf-8
"""Unit tests for :mod:`pulp_smash.utils`."""
from __future__ import unicode_literals

from pulp_smash import utils
from unittest2 import TestCase


class UUID4TestCase(TestCase):
    """Test :meth:`pulp_smash.utils.uuid4`."""

    def test_type(self):
        """Assert the method returns a unicode string."""
        self.assertIsInstance(utils.uuid4(), type(''))
