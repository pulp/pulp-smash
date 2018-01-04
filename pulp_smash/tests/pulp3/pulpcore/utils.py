# coding=utf-8
"""Utilities for Pulpcore tests."""
from pulp_smash import utils
from pulp_smash.tests.pulp3.utils import (
    require_pulp_plugins,
    require_pulp_version,
)


def gen_repo():
    """Return a semi-random dict for use in creating a repository."""
    return {'name': utils.uuid4(), 'notes': {}}


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulpcore isn't installed."""
    require_pulp_version()
    require_pulp_plugins({'pulpcore'})
