# coding=utf-8
"""Utility functions for RPM API tests."""
from __future__ import unicode_literals

from pulp_smash import api, utils
from pulp_smash.compat import urljoin


def gen_repo():
    """Return a semi-random dict for use in creating an RPM repository."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'yum_importer',
        'notes': {'_repo-type': 'rpm-repo'},
    }


def gen_distributor():
    """Return a semi-random dict for use in creating a YUM distributor."""
    return {
        'auto_publish': False,
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'yum_distributor',
        'distributor_config': {
            'http': True,
            'https': True,
            'relative_url': utils.uuid4() + '/',
        },
    }


def sync_repo(server_config, href):
    """Sync the referenced repository. Return the raw server response.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param href: The path to the repository to sync.
    :returns: The server's response.
    """
    return api.Client(server_config).post(
        urljoin(href, 'actions/sync/'),
        {'override_config': {}}
    )
