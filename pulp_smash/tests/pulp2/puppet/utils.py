# coding=utf-8
"""Utilities for Puppet tests."""
from unittest import SkipTest

from pulp_smash import utils
from pulp_smash.pulp2.utils import (
    require_issue_3159,
    require_issue_3687,
    require_pulp_2,
    require_unit_types,
)


def set_up_module():
    """Skip tests if Pulp 2 isn't under test or if Puppet isn't installed."""
    require_pulp_2(SkipTest)
    require_issue_3159(SkipTest)
    require_issue_3687(SkipTest)
    require_unit_types({'puppet_module'}, SkipTest)


def os_is_f27(cfg, pulp_host=None):
    """Tell whether the given Pulp host's OS is F27."""
    return (utils.get_os_release_id(cfg, pulp_host) == 'fedora' and
            utils.get_os_release_version_id(cfg, pulp_host) == '27')
