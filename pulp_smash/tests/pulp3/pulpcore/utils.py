# coding=utf-8
"""Utilities for Pulpcore tests."""
from pulp_smash.tests.pulp3.utils import require_pulp_3, require_pulp_plugins


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulpcore isn't installed."""
    require_pulp_3()
    require_pulp_plugins({'pulpcore'})
