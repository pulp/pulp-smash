# coding=utf-8
"""Utility functions for Python API tests."""
from pulp_smash import utils


def gen_repo():
    """Return a semi-random dict for use in creating a Python repository."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'python_importer',
        'notes': {'_repo-type': 'PYTHON'},
    }


def gen_distributor():
    """Return a semi-random dict for use in creating a Python distributor."""
    return {
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'python_distributor',
    }
