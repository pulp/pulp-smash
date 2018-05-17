# coding=utf-8
"""Utilities for Puppet tests."""
from pulp_smash.pulp2 import utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test or if Puppet isn't installed."""
    utils.require_pulp_2()
    utils.require_issue_3159()
    utils.require_unit_types({'puppet_module'})
