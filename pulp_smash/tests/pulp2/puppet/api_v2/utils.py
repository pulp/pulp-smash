# coding=utf-8
"""Utility functions for Puppet API tests."""
from pulp_smash import utils


def gen_repo(**kwargs):
    """Return a semi-random dict that used for creating a puppet repo."""
    data = {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'puppet_importer',
        'notes': {'_repo-type': 'puppet-repo'}
    }
    data.update(kwargs)
    return data


def gen_distributor(**kwargs):
    """Return a semi-random dict for use in creating a Puppet distributor."""
    data = {
        'auto_publish': False,
        'distributor_config': {'serve_http': True, 'serve_https': True},
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'puppet_distributor'
    }
    data.update(kwargs)
    return data


def gen_install_distributor(**kwargs):
    """Return a semi-random dict used for creating a Puppet install distributor.

    The caller must fill the install_path distributor_config option otherwise
    Pulp will throw an error when creating the distributor.
    """
    data = {
        'auto_publish': False,
        'distributor_config': {},
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'puppet_install_distributor'
    }
    data.update(kwargs)
    return data
