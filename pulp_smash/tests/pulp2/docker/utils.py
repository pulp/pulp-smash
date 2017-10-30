# coding=utf-8
"""Utilities for Docker tests."""
from packaging.version import Version

from pulp_smash import utils
from pulp_smash.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_UPSTREAM_NAME_NOLIST,
)


def set_up_module():
    """Skip tests if the Docker plugin is not installed.

    See :mod:`pulp_smash.tests` for more information.
    """
    utils.set_up_module()
    utils.skip_if_type_is_unsupported('docker_image')


def get_upstream_name(cfg):
    """Return a Docker upstream name.

    Return :data:`pulp_smash.constants.DOCKER_UPSTREAM_NAME_NOLIST` if Pulp is
    older than version 2.14. Otherwise, return
    :data:`pulp_smash.constants.DOCKER_UPSTREAM_NAME`. See the documentation
    for those constants for more information.
    """
    if cfg.pulp_version < Version('2.14'):
        return DOCKER_UPSTREAM_NAME_NOLIST
    return DOCKER_UPSTREAM_NAME
