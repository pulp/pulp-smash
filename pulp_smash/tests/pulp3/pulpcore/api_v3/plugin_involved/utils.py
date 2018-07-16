# coding=utf-8
"""Utilities for pulpcore API tests that require the file plugin."""
from urllib.parse import urljoin

from pulp_smash import api, utils
from pulp_smash.constants import FILE_FEED_URL
from pulp_smash.pulp3.constants import (
    FILE_CONTENT_PATH,
    FILE_REMOTE_PATH,
    REPO_PATH,
)
from pulp_smash.pulp3.utils import gen_repo, gen_remote, sync


def gen_publisher(**kwargs):
    """Return a semi-random dict for use in creating a publisher."""
    data = {'name': utils.uuid4()}
    data.update(kwargs)
    return data


def populate_pulp(cfg, url=None):
    """Add file contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp
        application.
    :param url: The URL to a file repository's ``PULP_MANIFEST`` file. Defaults
        to :data:`pulp_smash.constants.FILE_FEED_URL` + ``PULP_MANIFEST``.
    :returns: A list of dicts, where each dict describes one file content in
        Pulp.
    """
    if url is None:
        url = urljoin(FILE_FEED_URL, 'PULP_MANIFEST')
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(client.post(FILE_REMOTE_PATH, gen_remote(url)))
        repo.update(client.post(REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['_href'])
        if repo:
            client.delete(repo['_href'])
    return client.get(FILE_CONTENT_PATH)['results']
