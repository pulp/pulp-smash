# coding=utf-8
"""Utilities for interacting with OS tree."""
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


def gen_distributor():
    """Return a semi-random dict for use in creating an OSTree distributor.

    For more information, see the generic `repository CRUD`_ documentation and
    the OSTree `distributor configuration`_ documentation.

    .. NOTE: The OSTree `distributor configuration`_ documentation doesn't list
        the available parameters. To discover which parameters are available,
        execute ``pulp-admin -vv ostree repo create …``. See `Pulp #2254`_.

    .. _repository CRUD:
        http://docs.pulpproject.org/dev-guide/integration/rest-api/repo/cud.html
    .. _distributor configuration:
        http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/distributor.html
    .. _Pulp #2254: https://pulp.plan.io/issues/2254
    """
    return {
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'ostree_web_distributor',
    }
