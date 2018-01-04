# coding=utf-8
"""Utilities for tests for the file plugin."""
from pulp_smash.tests.pulp3.utils import (
    require_pulp_plugins,
    require_pulp_version,
)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp-file isn't installed."""
    require_pulp_version()
    require_pulp_plugins({'pulp-file'})
