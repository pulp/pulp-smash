# coding=utf-8
"""Utilities for file plugin tests."""
from pulp_smash import utils
from pulp_smash.tests.pulp3.utils import get_content


def gen_publisher():
    """Return a semi-random dict for use in creating a publisher."""
    return {'name': utils.uuid4()}


def get_content_unit_paths(repo):
    """Return the relative path of content units present in a file repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit['relative_path']  # file path and name
        for content_unit in get_content(repo)['results']
    ]
