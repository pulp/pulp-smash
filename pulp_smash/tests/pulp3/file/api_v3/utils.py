# coding=utf-8
"""Utilities for file plugin tests."""
from random import choice, sample

from pulp_smash.tests.pulp3.constants import (
    IMPORTER_DOWN_POLICY,
    IMPORTER_SYNC_MODE,
)
from pulp_smash import utils


def gen_importer(repo):
    """Return a semi-random dict for use in creating an importer.

    :param repo: A dict of information about a file repository.
    """
    return {
        'download_policy': sample(IMPORTER_DOWN_POLICY, 1)[0],
        'name': utils.uuid4(),
        'repository': repo['_href'],
        'sync_mode': sample(IMPORTER_SYNC_MODE, 1)[0],
    }


def gen_publisher(repo):
    """Return a semi-random dict for use in creating a publisher.

    :param repo: A dict of information about a file repository.
    """
    return {
        'name': utils.uuid4(),
        'repository': repo['_href'],
        'auto_publish': choice((False, True))
    }
