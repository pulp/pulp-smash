# coding=utf-8
"""Utilities for Python tests."""
from pulp_smash import utils


def set_up_module():
    """Skip tests if the Python plugin is not installed.

    See :mod:`pulp_smash.pulp2.tests` for more information.
    """
    utils.skip_if_type_is_unsupported('python_package')
