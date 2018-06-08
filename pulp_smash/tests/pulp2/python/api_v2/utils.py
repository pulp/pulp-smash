# coding=utf-8
"""Utility functions for Python API tests."""
from pulp_smash import utils


def gen_repo(**kwargs):
    """Return a semi-random dict for use in creating a Python repository."""
    data = {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'python_importer',
        'notes': {'_repo-type': 'PYTHON'}
    }
    data.update(kwargs)
    return data


def gen_distributor(**kwargs):
    """Return a semi-random dict for use in creating a Python distributor."""
    data = {
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'python_distributor'
    }
    data.update(kwargs)
    return data
