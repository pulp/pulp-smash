# coding=utf-8
"""Utility functions for Pulp 3 tests."""
import random
import unittest
import warnings
from copy import deepcopy
from urllib.parse import urljoin, urlsplit

from packaging.version import Version
from requests.auth import AuthBase, HTTPBasicAuth

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import (
    JWT_PATH,
    ORPHANS_PATH,
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
    :returns: A set of plugin names, e.g. ``{'pulpcore', 'pulp_file'}``.
    """
    if not cfg:
        cfg = config.get_config()
    client = api.Client(cfg, api.json_handler)
    return {
        version['component'] for version in client.get(STATUS_PATH)['versions']
    }


def sync(cfg, remote, repo):
    """Sync a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param remote: A dict of information about the remote of the repository
        to be synced.
    :param repo: A dict of information about the repository.
    :returns: The server's response. Call ``.json()`` on the response to get
        a call report.
    """
    return api.Client(cfg, api.json_handler).post(
        urljoin(remote['_href'], 'sync/'), {'repository': repo['_href']}
    )


def publish(cfg, publisher, repo, version_href=None):
    """Publish a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param publisher: A dict of information about the publisher of the
        repository to be published.
    :param repo: A dict of information about the repository.
    :param version_href: The repository version to be published.
    :returns: A publication. A dict of information about the just created
        publication.
    """
    if version_href is None:
        body = {'repository': repo['_href']}
    else:
        body = {'repository_version': version_href}
    client = api.Client(cfg, api.json_handler)
    call_report = client.post(urljoin(publisher['_href'], 'publish/'), body)
    # As of this writing, Pulp 3 only returns one task. If Pulp 3 starts
    # returning multiple tasks, this may need to be re-written.
    tasks = tuple(api.poll_spawned_tasks(cfg, call_report))
    if len(tasks) != 1:
        message = (
            'Multiple tasks were spawned in response to API call. This is '
            'unexpected, and Pulp Smash may handle the response incorrectly. '
            'Here is the tasks generated: {}'
        )
        message = message.format(tasks)
        warnings.warn(message, RuntimeWarning)
    return client.get(tasks[-1]['created_resources'][0])


def get_content(repo, version_href=None):
    """Read the content units of a given repository.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read. If none, read the
        latest repository version.
    :returns: A dict of information about the content units present in a given
        repository version.
    """
    if version_href is None:
        version_href = repo['_latest_version_href']
    return (api
            .Client(config.get_config(), api.json_handler)
            .get(urljoin(version_href, 'content/')))


def get_added_content(repo, version_href=None):
    """Read the added content of a given repository version.

    :param repo: A dict of information about a repository.
    :param version_href: The repository version to read. If none, read the
        latest repository version.
    :returns: A dict of information about the content added since the previous
        repository version.
    """
    if version_href is None:
        version_href = repo['_latest_version_href']
    return (api
            .Client(config.get_config(), api.json_handler)
            .get(urljoin(version_href, 'added_content/')))


def get_removed_content(repo, version_href=None):
    """Read the removed content of a given repository version.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read. If none, read the
        latest repository version.
    :returns: A dict of information about the content removed since the
        previous repository version.
    """
    if version_href is None:
        version_href = repo['_latest_version_href']
    return (api
            .Client(config.get_config(), api.json_handler)
            .get(urljoin(version_href, 'removed_content/')))


def delete_orphans(cfg=None):
    """Clean all content units present in pulp.

    An orphaned artifact is an artifact that is not in any content units.
    An orphaned content unit is a content unit that is not in any repository
    version.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
     host.
    """
    if cfg is None:
        cfg = config.get_config()
    api.Client(cfg, api.safe_handler).delete(ORPHANS_PATH)


def get_versions(repo, params=None):
    """Return repository versions, sorted by version ID.

    :param repo: A dict of information about the repository.
    :param params: Dictionary or bytes to be sent in the query string. Used to
        filter which versions are returned.
    :returns: A sorted list of dicts of information about repository versions.
    """
    versions = (
        api
        .Client(config.get_config(), api.json_handler)
        .get(repo['_versions_href'], params=params)['results'])
    versions.sort(
        key=lambda version: int(urlsplit(version['_href']).path.split('/')[-2])
    )
    return versions


def get_artifact_paths(repo, version_href=None):
    """Return the paths of artifacts present in a given repository version.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read.
    :returns: A set with the paths of units present in a given repository.
    """
    return {
        content_unit['artifact']  # file path and name
        for content_unit in get_content(repo, version_href)['results']
    }


def delete_version(repo, version_href=None):
    """Delete a given repository version.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version that should be
        deleted.
    :returns: A tuple. The tasks spawned by Pulp.
    """
    if version_href is None:
        version_href = repo['_latest_version_href']
    cfg = config.get_config()
    client = api.Client(cfg, api.json_handler)
    call_report = client.delete(version_href)
    # As of this writing, Pulp 3 only returns one task. If Pulp 3 starts
    # returning multiple tasks, this may need to be re-written.
    return tuple(api.poll_spawned_tasks(cfg, call_report))


def gen_distribution():
    """Return a semi-random dict for use in creating a distribution."""
    return {'base_path': utils.uuid4(), 'name': utils.uuid4()}


def gen_remote(url):
    """Return a semi-random dict for use in creating an remote.

    :param url: The URL of an external content source.
    """
    return {'name': utils.uuid4(), 'url': url}


def gen_repo():
    """Return a semi-random dict for use in creating a repository."""
    return {'name': utils.uuid4(), 'notes': {}}
