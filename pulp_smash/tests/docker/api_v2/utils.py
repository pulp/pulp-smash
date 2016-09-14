# coding=utf-8
"""Utility functions for Docker API tests."""
from pulp_smash import utils


def gen_repo():
    """Return a semi-random dict that used for creating a Docker repo."""
    return {
        'id': utils.uuid4(), 'importer_config': {},
        'importer_type_id': 'docker_importer',
        'notes': {'_repo-type': 'docker-repo'},
    }
