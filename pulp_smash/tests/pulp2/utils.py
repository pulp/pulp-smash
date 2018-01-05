# coding=utf-8
"""Utility functions for Pulp 2 tests."""
import unittest

from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp2.constants import PLUGIN_TYPES_PATH


def get_unit_types():
    """Tell which unit types are supported by the target Pulp server.

    Each Pulp plugin adds one (or more?) content unit types to Pulp, and each
    content unit type has a unique identifier. For example, the Python plugin
    [1]_ adds the Python content unit type [2]_, and Python content units have
    an ID of ``python_package``. This function queries the server and returns
    those unit type IDs.

    :returns: A set of content unit type IDs. For example: ``{'ostree',
        'python_package'}``.

    .. [1] http://docs.pulpproject.org/plugins/pulp_python/
    .. [2]
       http://docs.pulpproject.org/plugins/pulp_python/reference/python-type.html
    """
    unit_types = api.Client(config.get_config()).get(PLUGIN_TYPES_PATH).json()
    return {unit_type['id'] for unit_type in unit_types}


def require_pulp_2():
    """Skip tests if Pulp 2 isn't under test."""
    cfg = config.get_config()
    if cfg.pulp_version < Version('2') or cfg.pulp_version >= Version('3'):
        raise unittest.SkipTest(
            'These tests are for Pulp 2, but Pulp {} is under test.'
            .format(cfg.pulp_version)
        )


def require_unit_types(required_unit_types):
    """Skip tests if one or more unit types aren't supported.

    :param required_unit_types: A set of unit types IDs, e.g. ``{'ostree'}``.
    """
    missing_unit_types = required_unit_types - get_unit_types()
    if missing_unit_types:
        raise unittest.SkipTest(
            "The following unit types aren't supported by the Pulp "
            'application under test: {}'.format(missing_unit_types)
        )


def require_issue_3159():
    """Skip tests if Fedora 27 is under test and `Pulp #3159`_ is open.

    .. _Pulp #3159: https://pulp.plan.io/issues/3159
    """
    cfg = config.get_config()
    if (selectors.bug_is_untestable(3159, cfg.pulp_version) and
            utils.os_is_f27(cfg)):
        raise unittest.SkipTest('https://pulp.plan.io/issues/3159')
