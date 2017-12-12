# coding=utf-8
"""Utilities for file plugin tests."""
from random import sample

from pulp_smash.tests.pulp3.constants import (
    IMPORTER_DOWN_POLICY,
    IMPORTER_SYNC_MODE,
)
from pulp_smash import utils


def gen_importer():
    """Return a semi-random dict for use in creating an importer."""
    return {
        'name': utils.uuid4(),
        'download_policy': sample(IMPORTER_DOWN_POLICY, 1)[0],
        'sync_mode': sample(IMPORTER_SYNC_MODE, 1)[0],
    }


def modify_importer_down_policy(down_policy):
    """Return a valid download policy different from the given one."""
    return sample((IMPORTER_DOWN_POLICY - down_policy), 1)[0]


def modify_importer_sync_mode(sync_mode):
    """Return a valid sync mode different from the given one."""
    return sample((IMPORTER_SYNC_MODE - sync_mode), 1)[0]
