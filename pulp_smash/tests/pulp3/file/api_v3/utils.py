# coding=utf-8
"""Utilities for file plugin tests."""
from random import choice, sample

from pulp_smash.tests.pulp3.constants import (
    IMPORTER_DOWN_POLICY,
    IMPORTER_SYNC_MODE,
)
from pulp_smash import config, selectors, utils


def get_importer_down_policy():
    """Return the download policies that are available to the file plugin.

    See `Pulp #3320 <https://pulp.plan.io/issues/3320>`_.

    :returns: A subset of
        :data:`pulp_smash.tests.pulp3.constants.IMPORTER_DOWN_POLICY`. (The
        constant itself might be returned.)
    """
    if selectors.bug_is_untestable(3320, config.get_config()):
        return IMPORTER_DOWN_POLICY - {'background', 'on_demand'}
    return IMPORTER_DOWN_POLICY


def gen_importer():
    """Return a semi-random dict for use in creating an importer."""
    return {
        'download_policy': sample(get_importer_down_policy(), 1)[0],
        'name': utils.uuid4(),
        'sync_mode': sample(IMPORTER_SYNC_MODE, 1)[0],
    }


def gen_publisher():
    """Return a semi-random dict for use in creating a publisher."""
    return {
        'name': utils.uuid4(),
        'auto_publish': choice((False, True))
    }
