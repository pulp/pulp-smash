# coding=utf-8
"""Utilities for interacting with OS tree."""
from __future__ import unicode_literals

from pulp_smash import utils


def set_up_module():
    """Skip tests if the OSTree plugin is not installed.

    See :mod:`pulp_smash.tests` for more information.
    """
    utils.skip_if_type_is_unsupported('ostree')


def gen_repo():
    """Return a semi-random dict for use in creating an OSTree repository."""
    return {
        'id': utils.uuid4(),
        'importer_type_id': 'ostree_web_importer',
        'importer_config': {},
        'distributors': [],
        'notes': {'_repo-type': 'OSTREE'},
    }
