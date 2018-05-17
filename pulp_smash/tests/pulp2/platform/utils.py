# coding=utf-8
"""Utilities for platform tests."""
import unittest

from pulp_smash import config
from pulp_smash.pulp2 import utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test."""
    utils.require_pulp_2()
    utils.require_issue_3159()


def require_selinux():
    """Test if selinux is disabled in config.

    Note: We expect selinux tests are always run. However some test environments
    (such as OSX + Container) selinux is unsupported. Tests should be skipped in this case.
    See `pulp_smash.Config``
    """
    cfg = config.get_config()
    assert cfg.pulp_selinux_enabled is not None, 'pulp_selinux_enabled must be True or False'
    if not cfg.pulp_selinux_enabled:
        raise unittest.SkipTest("Selinux tests disabled by user's settings.json")
