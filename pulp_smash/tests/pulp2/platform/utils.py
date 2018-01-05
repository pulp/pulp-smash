# coding=utf-8
"""Utilities for platform tests."""
from pulp_smash.tests.pulp2 import utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test."""
    utils.require_pulp_2()
    utils.require_issue_3159()
