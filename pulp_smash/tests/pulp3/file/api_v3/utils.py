# coding=utf-8
"""Utilities for file plugin tests."""
from pulp_smash import utils


def gen_remote():
    """Return a semi-random dict for use in creating an remote."""
    return {
        'name': utils.uuid4(),
    }


def gen_publisher():
    """Return a semi-random dict for use in creating a publisher."""
    return {
        'name': utils.uuid4(),
    }
