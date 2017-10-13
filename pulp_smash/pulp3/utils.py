# coding=utf-8
"""Utility functions for Pulp3 tests."""
from urllib.parse import urljoin, urlsplit, urlunsplit

from requests.auth import AuthBase

from pulp_smash import config


class JWTAuth(AuthBase):
    """An extender of requests ``AuthBase`` class.

    See:

    ``Custom Authentication`` Requests library. See `example
    <http://docs.python-requests.org/en/latest/user/advanced/#custom-authentication>`_.
    """

    def __init__(self, token, header_format='Bearer'):
        """Require token variable."""
        self.token = token
        self.header_format = header_format

    def __call__(self, request):
        """Modify header and return request."""
        request.headers['Authorization'] = (
            self.header_format + ' ' + self.token
        )
        return request


def get_base_url():
    """Return the base url from settings."""
    cfg = config.get_config()
    pulp_system = cfg.get_systems('api')[0]
    return '{}://{}/'.format(
        pulp_system.roles['api'].get('scheme', 'https'),
        pulp_system.hostname
    )


def get_url(base_url, path):
    """Return joined base_url and path."""
    return urljoin(base_url, path)


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

# TODO create function to verify Pulp Version
