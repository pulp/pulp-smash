# coding=utf-8
"""Tests for core functionality that require plugin involvement to exercise."""

from unittest import SkipTest

from pulp_smash.pulp3.utils import require_pulp_3, require_pulp_plugins


def set_up_module():
    """Conditions to skip tests.

    Skip tests if not testing Pulp 3, or if either pulpcore or pulp_file
    aren't installed.
    """
    require_pulp_3(SkipTest)
    require_pulp_plugins({'pulpcore', 'pulp_file'}, SkipTest)
