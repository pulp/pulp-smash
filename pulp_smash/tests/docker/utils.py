# coding=utf-8
"""Utilities for Docker tests."""
from __future__ import unicode_literals

from pulp_smash import utils


def set_up_module():
    """Skip tests if the Docker plugin is not installed.

    See :mod:`pulp_smash.tests` for more information.
    """
    utils.skip_if_type_is_unsupported('docker_image')
