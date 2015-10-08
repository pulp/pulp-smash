# coding=utf-8
"""Unit tests for :mod:`pulp_smash.config.mixins`."""
from __future__ import unicode_literals

import mock
from pulp_smash.config.base import ConfigSection
from pulp_smash.config.mixins import AuthMixin
from unittest2 import TestCase


class ConfigWithAuthMixin(AuthMixin, ConfigSection):
    """A class inheriting from ``AuthMixin`` and ``ConfigSection``."""
    pass


class AuthMixinTestCase(TestCase):
    """Tests for :class:`pulp_smash.config.mixins.AuthMixin`."""

    def test_auth_missing(self):
        """If the base method doesn't return "auth", none should be added."""
        with mock.patch.object(ConfigSection, 'read') as read:
            read.return_value = ConfigSection()
            self.assertNotIn('auth', ConfigWithAuthMixin().read())

    def test_auth_nonlist(self):
        """If "auth" is not a list, it should not be altered."""
        with mock.patch.object(ConfigSection, 'read') as read:
            read.return_value = ConfigSection(auth='foo')
            self.assertEqual(ConfigWithAuthMixin().read()['auth'], 'foo')

    def test_auth_list(self):
        """If "auth" is a list, it should be cast to a tuple."""
        with mock.patch.object(ConfigSection, 'read') as read:
            read.return_value = ConfigSection(auth=['foo'])
            self.assertEqual(ConfigWithAuthMixin().read()['auth'], ('foo',))
