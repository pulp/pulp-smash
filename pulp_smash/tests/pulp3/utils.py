# coding=utf-8
"""Utility functions for Pulp 3 tests."""
import random
import unittest
from copy import deepcopy
from urllib.parse import urljoin

from packaging.version import Version
from requests.auth import AuthBase, HTTPBasicAuth
from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors
from pulp_smash.tests.pulp3.constants import (
    ARTIFACTS_PATH,
    FILE_CONTENT_PATH,
    FILE_IMPORTER_PATH,
    JWT_PATH,
    STATUS_PATH,
)


# _get_jwt_auth() uses this as a cache. It is intentionally a global. This
# design lets us do interesting things like flush the cache at run time or
# completely avoid a config file by fetching values from the UI.
_JWT_AUTH = None


class JWTAuth(AuthBase):  # pylint:disable=too-few-public-methods
    """A class that enables JWT authentication with the Requests library.

    For more information, see the Requests documentation on `custom
    authentication
    <http://docs.python-requests.org/en/latest/user/advanced/#custom-authentication>`_.
    """

    def __init__(self, token, header_format='Bearer'):
        """Require token variable."""
        self.token = token
        self.header_format = header_format

    def __call__(self, request):
        """Modify header and return request."""
        request.headers['Authorization'] = ' '.join((
            self.header_format,
            self.token,
        ))
        return request


def require_pulp_3():
    """Skip tests if Pulp 3 isn't under test."""
    cfg = config.get_config()
    if cfg.pulp_version < Version('3') or cfg.pulp_version >= Version('4'):
        raise unittest.SkipTest(
            'These tests are for Pulp 3, but Pulp {} is under test.'
            .format(cfg.pulp_version)
        )


def require_pulp_plugins(required_plugins):
    """Skip tests if one or more plugins are missing.

    :param required_plugins: A set of plugin names, e.g. ``{'pulp-file'}``.
    """
    missing_plugins = required_plugins - get_plugins()
    if missing_plugins:
        raise unittest.SkipTest(
            'The following plugins are required but not installed: {}'
            .format(missing_plugins)
        )


def get_auth(cfg=None):
    """Return a random authentication object.

    By default, :class:`pulp_smash.api.Client` uses the same authentication
    method (HTTP BASIC) for every request. While this is a sane default, it
    doesn't let tests exercise other authentication procedures. This function
    returns a random authentication object. To demonstrate how this object can
    be used, here's an example showing how to create a user:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import get_config
    >>> from pulp_smash.tests.pulp3.utils import get_auth
    >>> from pulp_smash.tests.pulp3.constants import USER_PATH
    >>> cfg = config.get_config()
    >>> client = api.Client(cfg, api.json_handler)
    >>> client.request_kwargs['auth'] = get_auth()
    >>> client.post(USER_PATH, {
    >>>     'username': 'superuser',
    >>>     'password': 'admin',
    >>>     'is_superuser': True
    >>> })

    The returned object can also be used directly with `Requests`_. For more
    information, see the For more information, see the `Requests
    Authentication`_ documentation.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp app.
    :returns: A random authentication object.

    .. _Requests Authentication:
        http://docs.python-requests.org/en/master/user/authentication/
    .. _Requests: http://docs.python-requests.org/en/master/
    """
    if not cfg:
        cfg = config.get_config()
    choices = [_get_basic_auth]
    if selectors.bug_is_testable(3248, cfg.pulp_version):
        choices.append(_get_jwt_auth)
    return random.choice(choices)(cfg)


def _get_basic_auth(cfg):
    """Return an object for HTTP basic authentication."""
    return HTTPBasicAuth(cfg.pulp_auth[0], cfg.pulp_auth[1])


def _get_jwt_auth(cfg):
    """Return an object for JWT authentication.

    This function makes use of a cache. If possible, this cache will return a
    copy of an already-generated JWT authentication object. This can be
    problematic if, say, Pulp is reset and old authentication tokens are
    invalidated. To flush the cache, set the cache to ``None``.
    """
    global _JWT_AUTH  # pylint:disable=global-statement
    if not _JWT_AUTH:
        token = api.Client(cfg, api.json_handler).post(JWT_PATH, {
            'username': cfg.pulp_auth[0],
            'password': cfg.pulp_auth[1],
        })
        _JWT_AUTH = JWTAuth(token['token'])
    return deepcopy(_JWT_AUTH)


def get_plugins(cfg=None):
    """Return the set of plugins installed on the Pulp application.

    Pulp's API endpoint for reporting plugins and their versions doesn't work
    correctly at this time. Some hacks are implemented to discover which
    plugins are installed. As a result, not all plugins are returned.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        application under test.
    :returns: A set of plugin names, e.g. ``{'pulpcore', 'pulp-file'}``.
    """
    if not cfg:
        cfg = config.get_config()
    client = api.Client(cfg, api.json_handler)
    plugins = {
        version['component'] for version in client.get(STATUS_PATH)['versions']
    }

    # As of this writing, only the pulpcore plugin reports its existence.
    try:
        client.get(FILE_IMPORTER_PATH)
        plugins.add('pulp-file')  # Name of PyPI package.
    except HTTPError:
        pass

    return plugins


def sync_repo(cfg, importer, repo):
    """Sync a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param importer: A dict of information about the importer of the repository
        to be synced.
    :param repo: A dict of information about the repository.
    :returns: The server's response. Call ``.json()`` on the response to get
        a call report.
    """
    return api.Client(cfg, api.json_handler).post(
        urljoin(importer['_href'], 'sync/'), {'repository': repo['_href']}
    )


def publish_repo(cfg, publisher, repo, version=None):
    """Publish a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param publisher: A dict of information about the publisher of the
        repository to be published.
    :param repo: A dict of information about the repository.
    :param version: An integer specifying what repository version should be
        published.
    :returns: A publication. A dict of information about the just created
        publication.
    """
    if version is None:
        body = {'repository': repo['_href']}
    else:
        version_href = urljoin(repo['_versions_href'], str(version) + '/')
        body = {'repository_version': version_href}
    client = api.Client(cfg, api.json_handler)
    call_report = client.post(urljoin(publisher['_href'], 'publish/'), body)
    # As of this writing, Pulp 3 only returns one task. If Pulp 3 starts
    # returning multiple tasks, this may need to be re-written.
    last_task = next(api.poll_spawned_tasks(cfg, call_report))
    return client.get(last_task['created_resources'][0])


def get_latest_repo_version(repo):
    """Get the latest version of a given repository.

    :param repo: A dict of information about the repository.
    :returns: A _href to the latest version of a given repository.
    """
    return (api
            .Client(config.get_config(), api.json_handler)
            .get(repo['_href'])['_latest_version_href'])


def read_repo_content(repo, version=None):
    """Read the content units of a given repository.

    In case the repository version is not provided, the content of latest
    repository version will be read.

    :param repo: A dict of information about the repository.
    :param version: An integer specifying what repository version should be
        read.
    :returns: A dict of information about the content units present in a given
        repository version.
    """
    if version is None:
        version_href = get_latest_repo_version(repo)
    else:
        version_href = urljoin(repo['_versions_href'], str(version) + '/')
    return (api
            .Client(config.get_config(), api.json_handler)
            .get(urljoin(version_href, 'content/')))


def get_content_unit_paths(repo):
    """Return the relative path of content units present in a given repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit['relative_path']  # file path and name
        for content_unit in read_repo_content(repo)['results']
    ]


def clean_artifacts(cfg=None):
    """Clean all artifacts present in pulp.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    """
    if cfg is None:
        cfg = config.get_config()
    clean_content_units(cfg)
    client = api.Client(cfg, api.json_handler)
    for artifact in client.get(ARTIFACTS_PATH)['results']:
        client.delete(artifact['_href'])


def clean_content_units(cfg=None):
    """Clean all content units present in pulp.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
     host.
    """
    if cfg is None:
        cfg = config.get_config()
    client = api.Client(cfg, api.json_handler)
    for content_unit in client.get(FILE_CONTENT_PATH)['results']:
        client.delete(content_unit['_href'])
