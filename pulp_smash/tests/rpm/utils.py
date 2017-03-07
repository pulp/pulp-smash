# coding=utf-8
"""Utilities for RPM tests."""
import json

import requests
from packaging.version import Version

from pulp_smash import cli, config, selectors, utils
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


def check_issue_2277(cfg):
    """Return true if `Pulp #2277`_ affects the targeted Pulp system.

    :param pulp_smash.config.ServerConfig cfg: The Pulp system under test.

    .. _Pulp #2277: https://pulp.plan.io/issues/2277
    """
    if (cfg.version >= Version('2.10') and
            selectors.bug_is_untestable(2277, cfg.version)):
        return True
    return False


def check_issue_2387(cfg):
    """Return true if `Pulp #2387`_ affects the targeted Pulp system.

    :param pulp_smash.config.ServerConfig cfg: The Pulp system under test.

    .. _Pulp #2387: https://pulp.plan.io/issues/2387
    """
    if (cfg.version >= Version('2.10') and os_is_rhel6(cfg) and
            selectors.bug_is_untestable(2387, cfg.version)):
        return True
    return False


def check_issue_2354(cfg):
    """Return true if `Pulp #2354`_ affects the targeted Pulp system.

    :param pulp_smash.config.ServerConfig cfg: The Pulp system under test.

    .. _Pulp #2354: https://pulp.plan.io/issues/2354
    """
    if (cfg.version >= Version('2.10') and
            selectors.bug_is_untestable(2354, cfg.version)):
        return True
    return False


def check_issue_2620(cfg):
    """Return true if `Pulp #2620`_ affects the targeted Pulp system.

    :param pulp_smash.config.ServerConfig cfg: The Pulp system under test.

    .. _Pulp #2620: https://pulp.plan.io/issues/2620
    """
    if (cfg.version >= Version('2.12') and
            selectors.bug_is_untestable(2620, cfg.version)):
        return True
    return False


def os_is_rhel6(cfg):
    """Return ``True`` if the server runs RHEL 6, or ``False`` otherwise.

    :param pulp_smash.config.ServerConfig cfg: Information about the system
        being targeted.
    :returns: True or false.
    """
    response = cli.Client(cfg, cli.echo_handler).run((
        'grep',
        '-i',
        'red hat enterprise linux server release 6',
        '/etc/redhat-release',
    ))
    return response.returncode == 0
