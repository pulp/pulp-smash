# coding=utf-8
"""Utility functions for Pulp 3 tests."""
import random
import unittest
from urllib.parse import urlsplit, urlunsplit

from packaging.version import Version
from requests.auth import AuthBase, HTTPBasicAuth

from pulp_smash import api, config
from pulp_smash.tests.pulp3.constants import JWT_PATH


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


def get_base_url():
    """Return the base url from settings."""
    cfg = config.get_config()
    pulp_system = cfg.get_systems('api')[0]
    return '{}://{}/'.format(
        pulp_system.roles['api'].get('scheme', 'https'),
        pulp_system.hostname
    )


def adjust_url(url):
    """Return a URL that can be used for talking in a certain port.

    The URL returned is the same as ``url``, except that the scheme is set
    to HTTP, and the port is set to 8000.

    :param url: A string, such as ``https://pulp.example.com/foo``.
    :returns: A string, such as ``http://pulp.example.com:8000/foo``.
    """
    parse_result = urlsplit(url)
    netloc = parse_result[1].partition(':')[0] + ':8000'
    return urlunsplit(('http', netloc) + parse_result[2:])


def set_up_module():
    """Skip tests if Pulp 3 isn't under test."""
    cfg = config.get_config()
    if cfg.version < Version('3'):
        raise unittest.SkipTest(
            'These tests are for Pulp 3 or newer, but Pulp {} is under test.'
            .format(cfg.version)
        )


def get_auth():
    """Return a **random** authentication method.

    The use of this function will avoid the need to duplicate tests to cover
    the different methods of authentication. Since this function will return
    a random authentication method chosen between **Basic Auth** and **JWT**.

    As an example of basic usage, let`s say that you`d like to create a user.

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import get_config
    >>> from pulp_smash.tests.pulp3.utils import get_auth
    >>> from pulp_smash.tests.pulp3.constants import USER_PATH
    >>> cfg = config.get_config()
    >>> client = api.Client(cfg, api.json_handler)
    >>> client.post(USER_PATH, {
    >>>     'username': 'superuser',
    >>>     'password': 'admin',
    >>>     'is_superuser': True
    >>>     },
    >>>    auth=get_auth()
    >>> )

    In case of need to use a specific ``auth`` method, just use the regular
    methods.

    :returns: A random authentication method.
    """
    cfg = config.get_config()
    url = adjust_url(get_base_url())
    client = api.Client(cfg, api.json_handler)
    client.request_kwargs['url'] = url
    token = client.post(JWT_PATH, {
        'username': cfg.pulp_auth[0],
        'password': cfg.pulp_auth[1],
    })

    jwt_auth = JWTAuth(token['token'], 'JWT')
    basic_auth = HTTPBasicAuth(cfg.pulp_auth[0], cfg.pulp_auth[1])

    return random.choice([jwt_auth, basic_auth])
