# coding=utf-8
"""Utilities for Python tests."""
from functools import partial
from unittest import SkipTest

from pulp_smash import selectors
from pulp_smash.pulp2 import utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test or if Python isn't installed."""
    utils.require_pulp_2(SkipTest)
    utils.require_issue_3159(SkipTest)
    utils.require_issue_3687(SkipTest)
    utils.require_unit_types({'python_package'}, SkipTest)


skip_if = partial(selectors.skip_if, exc=SkipTest)  # pylint:disable=invalid-name
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
