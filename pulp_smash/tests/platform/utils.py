# coding=utf-8
"""Utilities for platform tests."""
from pulp_smash import utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test."""
    utils.set_up_module()
