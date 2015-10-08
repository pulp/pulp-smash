# coding=utf-8
"""Unit tests for :mod:`pulp_smash.config`."""
from __future__ import unicode_literals

from pulp_smash.config import ServerConfig
from unittest2 import TestCase


class InitTestCase(TestCase):
    """Tests for ``pulp_smash.config.ServerConfig.__init__``."""

    def test_arg_name(self):
        """Ensure the first arg is named ``base_url``."""
        config = ServerConfig('bar')
        self.assertEqual(config['base_url'], 'bar')
