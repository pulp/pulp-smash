# coding=utf-8
"""Utilities for Docker tests."""
import os
import json

from packaging.version import Version

from pulp_smash import cli, utils
from pulp_smash.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_UPSTREAM_NAME_NOLIST,
)
from pulp_smash.pulp2 import utils as pulp2_utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test or if Docker isn't installed."""
    pulp2_utils.require_pulp_2()
    pulp2_utils.require_issue_3159()
    pulp2_utils.require_unit_types({'docker_image'})


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


def write_manifest_list(cfg, manifest_list):
    """Write out a content source to JSON file.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp deployment on
        which to create a repository.
    :param manifest_list: A detailed dict of information about the manifest
        list.
    :return: The path to created file, and the path to dir that stores the
        file.
    """
    sudo = '' if utils.is_root(cfg) else 'sudo'
    client = cli.Client(cfg)
    dir_path = client.run('mktemp --directory'.split()).stdout.strip()
    file_path = os.path.join(dir_path, utils.uuid4() + '.json')
    manifest_list_json = json.dumps(manifest_list)
    client.machine.session().run(
        "{} echo '{}' > {}".format(
            sudo,
            manifest_list_json,
            file_path
        )
    )
    return file_path, dir_path
