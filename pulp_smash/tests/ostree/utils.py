# coding=utf-8
"""Utilities for interacting with OS tree."""
from __future__ import unicode_literals

import unittest2

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH


def skip_if_no_plugin():
    """Skip tests if the OSTree plugin is not installed.

    :raises: ``unittest2.SkipTest`` if the OSTree plugin is not installed on
        the default Pulp server.
    :returns: Nothing.
    """
    if 'ostree' not in utils.get_plugin_type_ids():
        raise unittest2.SkipTest('These tests require the OSTree plugin.')


def gen_repo():
    """Return a semi-random dict for use in creating an OSTree repository."""
    return {
        'id': utils.uuid4(),
        'importer_type_id': 'ostree_web_importer',
        'importer_config': {},
        'distributors': [],
        'notes': {'_repo-type': 'OSTREE'},
    }


def create_sync_repo(server_config, body):
    """Create and sync a repository.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param body: Data to encode as JSON and send as the body of the repository
        creation request.
    :returns: An iterable of ``(repo_href, sync_response)``. Note that
        ``sync_response.json()`` is a `call report`_.

    .. _call report:
        http://pulp.readthedocs.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report
    """
    client = api.Client(server_config)
    repo = client.post(REPOSITORY_PATH, body).json()
    # When a sync is requested, the default response handler (api.safe_handler)
    # will inspect the response (a call report), poll tasks until completion,
    # and inspect completed tasks. It's in our interest to let that happen
    # rather than redundantly pushing all those checks into test cases.
    response = client.post(
        urljoin(repo['_href'], 'actions/sync/'),
        {'override_config': {}},
    )
    return repo['_href'], response
