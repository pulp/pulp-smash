# coding=utf-8
"""Utilities for python plugin tests."""

from pulp_smash import utils
from pulp_smash.constants import PYTHON_PROJECT_LIST


def gen_remote():
    """Return a semi-random dict for use in creating an remote."""
    return {
        'name': utils.uuid4(),
        'projects': PYTHON_PROJECT_LIST,
    }


def gen_publisher():
    """Return a semi-random dict for use in creating a publisher."""
    return {
        'name': utils.uuid4(),
    }
