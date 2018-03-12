# coding=utf-8
"""Utilities for Pulpcore tests."""
import warnings

from pulp_smash import config, selectors, utils
from pulp_smash.tests.pulp3 import utils as pulp3_utils


def gen_repo():
    """Return a semi-random dict for use in creating a repository."""
    return {'name': utils.uuid4(), 'notes': {}}


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulpcore isn't installed."""
    pulp3_utils.require_pulp_3()
    pulp3_utils.require_pulp_plugins({'pulpcore'})


def gen_distribution():
    """Return a semi-random dict for use in creating a distribution."""
    if selectors.bug_is_testable(3412, config.get_config().pulp_version):
        warnings.warn(
            'The base_path field may be malformed. See: '
            'https://pulp.plan.io/issues/3412'
        )
    return {
        'base_path': utils.uuid4(),
        'name': utils.uuid4()
    }
