# coding=utf-8
"""Utility functions for Pulp 3 tests."""
import random
import unittest
from copy import deepcopy

from packaging.version import Version
from requests.auth import AuthBase, HTTPBasicAuth

from pulp_smash import api, config
from pulp_smash.tests.pulp3.constants import JWT_PATH


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


def set_up_module():
    """Skip tests if Pulp 3 isn't under test."""
    cfg = config.get_config()
    if cfg.pulp_version < Version('3'):
        raise unittest.SkipTest(
            'These tests are for Pulp 3 or newer, but Pulp {} is under test.'
            .format(cfg.pulp_version)
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
    return random.choice((_get_basic_auth, _get_jwt_auth))(cfg)


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
