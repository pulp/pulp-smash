# coding=utf-8
"""Utilities for Pulpcore tests."""
from pulp_smash import utils


def gen_repo():
    """Return a semi-random dict for use in creating a repository."""
    return {'name': utils.uuid4(), 'notes': {}}
