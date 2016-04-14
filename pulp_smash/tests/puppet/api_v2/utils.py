# coding=utf-8
"""Utility functions for Puppet API tests."""
from __future__ import unicode_literals

from pulp_smash import utils


def gen_repo():
    """Return a semi-random dict that used for creating a puppet repo."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'puppet_importer',
        'notes': {'_repo-type': 'puppet-repo'},
    }
