# coding=utf-8
"""Utilities for interacting with OS tree."""

import unittest2

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests if the OSTree plugin is not installed."""
    if 'ostree' not in utils.get_plugin_type_ids():
        raise unittest2.SkipTest('These tests require the OSTree plugin.')


def gen_repo():
    """Return OSTree repo body."""
    return {
        'id': utils.uuid4(),
        'importer_type_id': 'ostree_web_importer',
        'importer_config': {},
        'distributors': [],
        'notes': {'_repo-type': 'OSTREE'},
    }


def create_sync_repo(server_config, body):
    """Create repository."""
    client = api.Client(server_config, api.json_handler)
    repo = client.post(REPOSITORY_PATH, body)

    # Sync repository and collect task statuses.
    client.response_handler = api.echo_handler
    response = client.post(
        urljoin(repo['_href'], 'actions/sync/'),
        {'override_config': {}},
    )
    response.raise_for_status()
    tasks = tuple(api.poll_spawned_tasks(server_config, response.json()))
    return repo['_href'], response, tasks
