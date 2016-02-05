# coding=utf-8
"""Functional tests for Pulp's ostree plugin."""
from __future__ import unicode_literals

import os

from pulp_smash import api, config
from pulp_smash.constants import PLUGIN_TYPES_PATH


def _get_plugin_type_ids():
    """Get the ID of each of Pulp's plugins.

    Each Pulp plugin adds one (or more?) content unit type to Pulp. Each of
    these content unit types is identified by a certain unique identifier. For
    example, the `Python type`_ has an ID of ``python_package``.

    :returns: A set of plugin IDs. For example: ``{'ostree',
        'python_package'}``.

    .. _Python type:
       http://pulp-python.readthedocs.org/en/latest/reference/python-type.html
    """
    client = api.Client(config.get_config(), api.json_handler)
    plugin_types = client.get(PLUGIN_TYPES_PATH)
    return {plugin_type['id'] for plugin_type in plugin_types}


def load_tests(loader, standard_tests, pattern):
    """Load OSTree tests only if the plugin is installed on the target host.

    This method is called automatically by the unittest test runner. For more
    information, see documentation on the `load_tests Protocol
    <https://docs.python.org/3/library/unittest.html#load-tests-protocol>`_.

    This method may not work correctly on Pulp 2.8. See Pulp issue #1642, `List
    of Content Unit Types is Incomplete <https://pulp.plan.io/issues/1642>`_.
    """
    if 'ostree' in _get_plugin_type_ids():
        this_dir = os.path.dirname(__file__)
        package_tests = loader.discover(start_dir=this_dir, pattern=pattern)
        standard_tests.addTests(package_tests)
    return standard_tests
