# coding=utf-8
"""Utilities for RPM tests."""
from __future__ import unicode_literals

from pulp_smash import utils


def set_up_module():
    """Skip tests if the RPM plugin is not installed.

    See :mod:`pulp_smash.tests` for more information.
    """
    utils.skip_if_type_is_unsupported('rpm')
