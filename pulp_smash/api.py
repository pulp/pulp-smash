# coding=utf-8
"""Tools for working with Pulp's API."""
from __future__ import unicode_literals

import warnings
try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import requests

from pulp_smash import utils


_SENTINEL = object()


def _check_http_202_content_type(response):
    """Issue a warning if the content-type is not application/json."""
    if not (response.headers.get('Content-Type', '')
            .startswith('application/json')):
        _warn_http_202_content_type(response)


def _warn_http_202_content_type(response):
    """Issue a warning about the response status code."""
    if 'Content-Type' in response.headers:
        content_type = '"{}"'.format(response.headers['Content-Type'])
    else:
        content_type = 'not present'
    message = (
        'All HTTP 202 responses returned by Pulp should have a content-type '
        'of "application/json" and include a JSON call report. However, the '
        'Content-Type is {}. Here is the HTTP method, URL and headers from '
        'the request that generated this anomalous response: {} {} {}'
    )
    message = message.format(
        content_type,
        response.request.method,
        response.request.url,
        response.request.headers,
    )
    warnings.warn(message, RuntimeWarning)


def _handle_202(server_config, response):
    """Check for an HTTP 202 response and handle it appropriately."""
    if response.status_code == 202:  # "Accepted"
        _check_http_202_content_type(response)
        tuple(utils.poll_spawned_tasks(server_config, response.json()))


def echo_handler(server_config, response):  # pylint:disable=unused-argument
    """Immediately return ``response``."""
    return response


def safe_handler(server_config, response):
    """Check the response status code and wait for tasks to complete.

    Raise an exception if the response has an HTTP 4XX or 5XX status code. Wait
    for tasks to complete if the response has an HTTP Accepted status code.
    Return the response.
    """
    response.raise_for_status()
    _handle_202(server_config, response)
    return response


def json_handler(server_config, response):
    """Check status code, wait for tasks to complete, and return decoded JSON.

    Raise an exception if the response has an HTTP 4XX or 5XX status code. Wait
    for tasks to complete if the response has an HTTP Accepted status code.
    Return the response's decoded JSON body.
    """
    response.raise_for_status()
    _handle_202(server_config, response)
    return response.json()


class Client(object):
    """A convenience object for working with an API.

    This class is a wrapper around the ``requests.api`` module provided by
    `Requests`_. Each of the functions from that module are exposed as methods
    here, and each of the arguments accepted by Requests' functions are also
    accepted by these methods.

    The difference between this class and the `Requests`_ functions lies in its
    configurable request and response handling mechanisms. This class is
    flexible enough that it should be usable with any API, but certain defaults
    have been set to work well with `Pulp`_.

    As an example, let's say that you'd like to create a user, then read that
    user's information back from the server. This is one way to do it:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import get_config
    >>> client = Client(get_config())
    >>> response = client.post('/pulp/api/v2/users/', {'login': 'Alice'})
    >>> client.get(response.json()['_href'])

    This works, but handling raw responses can be kludgy. It is possible to set
    a custom callback function that handles responses differently. For example,
    the :func:`pulp_smash.api.json_handler` is much like the default
    :func:`pulp_smash.api.safe_handler`, except that it expects response bodies
    to be JSON and returns the decoded body:

    >>> from pulp_smash.api import Client, json_handler
    >>> from pulp_smash.config import get_config
    >>> client = Client(get_config(), json_handler)
    >>> attrs = client.post('/pulp/api/v2/users/', {'login': 'Alice'})
    >>> client.get(attrs['_href'])

    It is also possible to set request parameters, both on a per-client and
    per-request basis. Here is an example:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import ServerConfig
    >>> cfg = ServerConfig('http://example.com')
    >>> client = Client(cfg)
    >>> client.request_kwargs['url']  # copied from `cfg`
    'http://example.com'
    >>> client.request_kwargs['url'] = 'http://sub.example.com'
    >>> client.get('http://sub2.example.com')  # overrides `request_kwargs`
    >>> client.request_kwargs['url']  # but only for that one call
    'http://sub.example.com'

    As shown above, each client copies options from the
    :class:`pulp_smash.config.ServerConfig` given to it. New default arguments
    can then be set via the ``request_kwargs`` dict, and per-request arguments
    can also be set. What can be placed in ``request_kwargs``? Anything that
    the `Requests`_ functions accept. You can set ``verify``, ``auth`` and
    more.

    The ``url`` argument is slightly special. When making a call, it is
    possible to pass in a relative URL:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import get_config
    >>> client = Client(get_config())
    >>> response = client.get('/pulp/api/v2/')  # i.e. url='/pulp/api/v2/'

    What happens here? When a request is made, ``client.request_kwargs['url']``
    is joined to ``'/pulp/api/v2/'`` using ``urljoin`` (from the standard
    library). This allows one to easily use the hrefs returned by Pulp in
    constructing new requests. Refer back to the "users" example in this
    docstring as an example.

    The remainder of this docstring contains design notes. They should not be
    necessary for an end user, but may be useful to developers interested in
    hacking at this class.

    Requests' ``requests.api.post`` method has the following signature::

        def post(url, data=None, json=None, **kwargs)

    Pulp supports only JSON for most of its API endpoints, so it makes sense
    for us to demote ``data`` to being a regular kwarg and list ``json`` as the
    one and only positional argument.

    We make ``json`` a positional argument for ``post()``, ``put()`` and
    ``patch()``, but not the other methods. Why? Because HTTP OPTIONS, GET,
    HEAD and DELETE **must not** have bodies. This is stated by the HTTP/1.1
    specification, and network intermediaries such as caches are at liberty to
    drop such bodies.

    Why the sentinel? Imagine the following scenario: a user provides a default
    JSON payload in ``self.request_kwargs``, but they want to skip sending that
    payload for just one request. How can they do that? With ``client.post(url,
    None)``.

    .. _Pulp: http://www.pulpproject.org/
    .. _Requests: http://docs.python-requests.org/en/latest/
    """

    def __init__(
            self,
            server_config,
            response_handler=None,
            request_kwargs=None,
    ):
        """Initialize this object with needed instance attributes."""
        self._cfg = server_config
        self.request_kwargs = self._cfg.get_requests_kwargs()
        self.request_kwargs['url'] = self._cfg.base_url
        self.request_kwargs.update(
            {} if request_kwargs is None else request_kwargs
        )
        if response_handler is None:
            self.response_handler = safe_handler
        else:
            self.response_handler = response_handler

    def delete(self, url, **kwargs):
        """Send an HTTP DELETE request."""
        return self.request('DELETE', url, **kwargs)

    def get(self, url, **kwargs):
        """Send an HTTP GET request."""
        return self.request('GET', url, **kwargs)

    def head(self, url, **kwargs):
        """Send an HTTP HEAD request."""
        return self.request('HEAD', url, **kwargs)

    def options(self, url, **kwargs):
        """Send an HTTP OPTIONS request."""
        return self.request('OPTIONS', url, **kwargs)

    def patch(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP PATCH request."""
        if json is _SENTINEL:
            return self.request('PATCH', url, **kwargs)
        else:
            return self.request('PATCH', url, json=json, **kwargs)

    def post(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP POST request."""
        if json is _SENTINEL:
            return self.request('POST', url, **kwargs)
        else:
            return self.request('POST', url, json=json, **kwargs)

    def put(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP PUT request."""
        if json is _SENTINEL:
            return self.request('PUT', url, **kwargs)
        else:
            return self.request('PUT', url, json=json, **kwargs)

    def request(self, method, url, **kwargs):
        """Send an HTTP request.

        Arguments passed directly in to this method override (but do not
        overwrite!) arguments specified in ``self.request_kwargs``.
        """
        # The `self.request_kwargs` dict should *always* have a "url" argument.
        # This is enforced by `self.__init__`. This allows us to call the
        # `requests.request` function and satisfy its signature:
        #
        #     request(method, url, **kwargs)
        #
        request_kwargs = self.request_kwargs.copy()
        request_kwargs['url'] = urljoin(request_kwargs['url'], url)
        request_kwargs.update(kwargs)
        return self.response_handler(
            self._cfg,
            requests.request(method, **request_kwargs),
        )
