# coding=utf-8
"""Utilities for tests for the python plugin."""
from pulp_smash.tests.pulp3 import utils


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp-python isn't installed."""
    utils.require_pulp_3()
    utils.require_pulp_plugins({'pulp_python'})
