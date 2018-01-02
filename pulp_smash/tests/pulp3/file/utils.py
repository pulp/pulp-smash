# coding=utf-8
"""Utilities for tests for the file plugin."""
from pulp_smash.tests.pulp3 import utils


def set_up_module(cfg=None, required_plugins=None):
    """Skip tests Pulp 3 isn't under test or if pulp-file isn't installed."""
    if required_plugins is None:
        required_plugins = {'pulp-file'}
    utils.set_up_module(cfg, required_plugins)
