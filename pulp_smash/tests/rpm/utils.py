# coding=utf-8
"""Utilities for RPM tests."""
import json

import requests

from pulp_smash import config, selectors, utils
from pulp_smash.constants import RPM_ERRATUM_URL


def set_up_module():
    """Skip tests if the RPM plugin is not installed.

    See :mod:`pulp_smash.tests` for more information.
    """
    utils.skip_if_type_is_unsupported('rpm')


def gen_erratum():
    """Return an erratum with a randomized ID.

    Fetch, decode, munge and return the erratum file at
    :data:`pulp_smash.constants.RPM_ERRATUM_URL`. This erratum can be uploaded
    and imported into an RPM repository with
    :meth:`pulp_smash.utils.upload_import_erratum`.
    """
    response = requests.get(RPM_ERRATUM_URL)
    response.raise_for_status()
    erratum = json.loads(response.text)
    erratum['id'] = utils.uuid4()
    # "Cannot provide multiple checksums when uploading an erratum"
    if selectors.bug_is_untestable(2020, config.get_config().version):
        for package in erratum['pkglist'][0]['packages']:
            package['sum'] = package['sum'][:2]
    return erratum
