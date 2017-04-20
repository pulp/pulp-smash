# coding=utf-8
"""A client for working with Pulp's API.

Working with an API can require repetitive calls to perform actions like check
HTTP status codes. In addition, Pulp's API has specific quirks surrounding its
handling of href paths and HTTP 202 status codes. This module provides a
customizable client that makes it easier to work with the API in a safe and
concise manner.
"""
import warnings
from time import sleep
from urllib.parse import urljoin, urlparse

import requests

from pulp_smash import exceptions


_SENTINEL = object()
_TASK_END_STATES = ('canceled', 'error', 'finished', 'skipped', 'timed out')


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


def _check_call_report(call_report):
    """Inspect the given call report's ``error`` field.

    If the field is non-null, raise a ``CallReportError``.
    """
    if call_report['error'] is not None:
        raise exceptions.CallReportError(
            'A call report contains an error. Full call report: {}'
            .format(call_report)
        )


def _check_tasks(tasks):
    """Inspect each task's ``error``, ``exception`` and ``traceback`` fields.

    If any of these fields is non-null for any tasks, raise a
    ``TaskReportError``.
    """
    for task in tasks:
        for field in ('error', 'exception', 'traceback'):
            if task[field] is not None:
                msg = 'Task report {} contains a {}: {}\nFull task report: {}'
                msg = msg.format(task['_href'], field, task[field], task)
                raise exceptions.TaskReportError(msg, task)


def _handle_202(server_config, response):
    """Check for an HTTP 202 response and handle it appropriately."""
    if response.status_code == 202:  # "Accepted"
        _check_http_202_content_type(response)
        call_report = response.json()
        tasks = tuple(poll_spawned_tasks(server_config, call_report))
        _check_call_report(call_report)
        _check_tasks(tasks)


def echo_handler(server_config, response):  # pylint:disable=unused-argument
    """Immediately return ``response``."""
    return response


def safe_handler(server_config, response):
    """Check status code, wait for tasks to complete, and check tasks.

    Inspect the response's HTTP status code. If the response has an HTTP
    Accepted status code, inspect the returned call report, wait for each task
    to complete, and inspect each completed task.

    :raises: ``requests.exceptions.HTTPError`` if the response status code is
        in the 4XX or 5XX range.
    :raises pulp_smash.exceptions.CallReportError: If the call report contains
        an error.
    :raises pulp_smash.exceptions.TaskReportError: If the task report contains
        an error.
    """
    response.raise_for_status()
    _handle_202(server_config, response)
    return response


def json_handler(server_config, response):
    """Like ``safe_handler``, but also return a JSON-decoded response body.

    Do what :func:`pulp_smash.api.safe_handler` does. In addition, decode the
    response body as JSON and return the result.
    """
    response.raise_for_status()
    _handle_202(server_config, response)
    return response.json()


class Client(object):
    """A convenience object for working with an API.

    This class is a wrapper around the ``requests.api`` module provided by
    `Requests`_. Each of the functions from that module are exposed as methods
    here, and each of the arguments accepted by Requests' functions are also
    accepted by these methods. The difference between this class and the
    `Requests`_ functions lies in its configurable request and response
    handling mechanisms.

    This class is flexible enough that it should be usable with any API, but
    certain defaults have been set to work well with `Pulp`_.

    As an example of basic usage, let's say that you'd like to create a user,
    then read that user's information back from the server. This is one way to
    do it:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import get_config
    >>> client = Client(get_config())
    >>> response = client.post('/pulp/api/v2/users/', {'login': 'Alice'})
    >>> response = client.get(response.json()['_href'])
    >>> print(response.json())

    Notice how we never call ``response.raise_for_status()``? We don't need to
    because, by default, ``Client`` instances do this. Handy!

    How does this work? Each ``Client`` object has a callback function,
    ``response_handler``, that is given a chance to munge each server response.
    How else might this callback be useful? Well, notice how we call ``json()``
    on each server response? That's kludgy. Let's write our own callback that
    takes care of this for us:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import get_config
    >>> def response_handler(server_config, response):
    ...     response.raise_for_status()
    ...     return response.json()
    >>> client = Client(get_config(), response_handler=response_handler)
    >>> response = client.post('/pulp/api/v2/users/', {'login': 'Alice'})
    >>> response = client.get(response['_href'])
    >>> print(response)

    Pulp Smash ships with several response handlers. See:

    * :func:`pulp_smash.api.echo_handler`
    * :func:`pulp_smash.api.safe_handler`
    * :func:`pulp_smash.api.json_handler`

    As mentioned, this class has configurable request and response handling
    mechanisms. We've covered response handling mechanisms — let's move on to
    request handling mechanisms.

    When a client is instantiated, a :class:`pulp_smash.config.PulpSmashConfig`
    must be passed to the constructor, and configuration options are copied
    from the ``PulpSmashConfig`` to the client. These options can be overridden
    on a per-object or per-request basis. Here's an example:

    >>> from pulp_smash.api import Client
    >>> from pulp_smash.config import PulpSmashConfig
    >>> cfg = config.PulpSmashConfig(
    ...     pulp_auth=('username', 'password'),
    ...     systems=[
    ...         config.PulpSystem(
    ...             hostname='example.com',
    ...             roles={'api': {
    ...                'scheme': 'https',
    ...                'verify': '~/Documents/my.crt',
    ...             }}
    ...         )
    ...     ]
    ... )
    >>> client = api.Client(cfg)
    >>> client.request_kwargs['url'] == 'https://example.com'
    True
    >>> client.request_kwargs['verify'] == '~/Documents/my.crt'
    True
    >>> response = client.get('/index.html')  # Use my.crt for SSL verification
    >>> response = client.get('/index.html', verify=False)  # Disable SSL
    >>> response = client.get('/index.html')  # Use my.crt for SSL verification
    >>> client.request_kwargs['verify'] = None
    >>> response = client.get('/index.html')  # Do default SSL verification

    Anything accepted by the `Requests`_ functions may be placed in
    ``request_kwargs`` or passed in to a specific call. You can set ``verify``
    for example.

    The ``url`` argument is slightly special. When making a call, it is
    possible to pass in a relative URL, as shown in the examples above. (e.g.
    ``/index.html``.) The default URL and passed-in URL are joined like so:

    >>> urljoin(request_kwargs['url'], passed_in_url)

    This allows one to easily use the hrefs returned by Pulp in constructing
    new requests.

    The remainder of this docstring contains design notes. They are useful to
    advanced users and developers.

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
            pulp_system=None,
    ):
        """Initialize this object with needed instance attributes."""
        if not pulp_system:
            pulp_system = server_config.get_systems('api')[0]
        self.pulp_system = pulp_system
        self._cfg = server_config
        self.request_kwargs = self._cfg.get_requests_kwargs(pulp_system)
        self.request_kwargs['url'] = self._cfg.get_base_url(pulp_system)
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
        return self.request('PATCH', url, json=json, **kwargs)

    def post(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP POST request."""
        if json is _SENTINEL:
            return self.request('POST', url, **kwargs)
        return self.request('POST', url, json=json, **kwargs)

    def put(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP PUT request."""
        if json is _SENTINEL:
            return self.request('PUT', url, **kwargs)
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
        cfg_host = urlparse(self._cfg.get_base_url(self.pulp_system)).hostname
        request_host = urlparse(request_kwargs['url']).hostname
        if request_host != cfg_host:
            warnings.warn(
                'This client was originally created for communicating with '
                '{0}, but a request is being made to {1}. The request will be '
                'made, but beware that information intended for {0} (such as '
                "authentication tokens) may now be sent to {1}. Here's the "
                'full list of options being sent with this request: {2}'
                .format(cfg_host, request_host, request_kwargs),
                RuntimeWarning
            )
        return self.response_handler(
            self._cfg,
            requests.request(method, **request_kwargs),
        )


def poll_spawned_tasks(server_config, call_report, pulp_system=None):
    """Recursively wait for spawned tasks to complete. Yield response bodies.

    Recursively wait for each of the spawned tasks listed in the given `call
    report`_ to complete. For each task that completes, yield a response body
    representing that task's final state.

    :param server_config: A :class:`pulp_smash.config.PulpSmashConfig` object.
    :param call_report: A dict-like object with a `call report`_ structure.
    :param pulp_system: The system from where to pool the task. If ``None`` is
        provided then the first system found with api role will be used.
    :returns: A generator yielding task bodies.
    :raises: Same as :meth:`poll_task`.

    .. _call report:
        http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report
    """
    if not pulp_system:
        pulp_system = server_config.get_systems('api')[0]
    hrefs = (task['_href'] for task in call_report['spawned_tasks'])
    for href in hrefs:
        for final_task_state in poll_task(server_config, href, pulp_system):
            yield final_task_state


def poll_task(server_config, href, pulp_system=None):
    """Wait for a task and its children to complete. Yield response bodies.

    Poll the task at ``href``, waiting for the task to complete. When a
    response is received indicating that the task is complete, yield that
    response body and recursively poll each child task.

    :param server_config: A :class:`pulp_smash.config.PulpSmashConfig` object.
    :param href: The path to a task you'd like to monitor recursively.
    :param pulp_system: The system from where to pool the task. If ``None`` is
        provided then the first system found with api role will be used.
    :returns: An generator yielding response bodies.
    :raises pulp_smash.exceptions.TaskTimedOutError: If a task takes too
        long to complete.
    """
    if not pulp_system:
        pulp_system = server_config.get_systems('api')[0]
    # 360 * 5s == 1800s == 30m
    # NOTE: The timeout counter is synchronous. We query Pulp, then count down,
    # then query pulp, then count down, etc. This is… dumb.
    poll_limit = 360
    poll_counter = 0
    while True:
        response = requests.get(
            urljoin(server_config.get_base_url(pulp_system), href),
            **server_config.get_requests_kwargs(pulp_system)
        )
        response.raise_for_status()
        attrs = response.json()
        if attrs['state'] in _TASK_END_STATES:
            # This task has completed. Yield its final state, then iterate
            # through each of its children and yield their final states.
            yield attrs
            for href_ in (task['_href'] for task in attrs['spawned_tasks']):
                for final_task_state in poll_task(server_config, href_):
                    yield final_task_state
            break
        poll_counter += 1
        if poll_counter > poll_limit:
            raise exceptions.TaskTimedOutError(
                'Task {} is ongoing after {} polls.'.format(href, poll_limit)
            )
        sleep(5)
