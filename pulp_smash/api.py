# coding=utf-8
"""A client for working with Pulp's API.

Working with an API can require repetitive calls to perform actions like check
HTTP status codes. In addition, Pulp's API has specific quirks surrounding its
handling of href paths and HTTP 202 status codes. This module provides a
customizable client that makes it easier to work with the API in a safe and
concise manner.
"""
import copy
import warnings
from time import sleep
from urllib.parse import urljoin, urlparse

import requests
from packaging.version import Version

from pulp_smash import exceptions
from pulp_smash.log import logger

_SENTINEL = object()
_TASK_END_STATES = ("canceled", "error", "finished", "skipped", "timed out")
_P3_TASK_END_STATES = ("canceled", "completed", "failed", "skipped")


def check_pulp3_restriction(client):
    """Check if running system is running on Pulp3 otherwise raise error."""
    if client._cfg.pulp_version < Version("3") or client._cfg.pulp_version >= Version("4"):
        raise ValueError(
            "This method is designed to handle responses returned by Pulp 3. "
            "However, the targeted Pulp application is declared as being "
            "version {}. Please use a different response handler.".format(client._cfg.pulp_version)
        )


def _check_http_202_content_type(response):
    """Issue a warning if the content-type is not application/json."""
    if not (response.headers.get("Content-Type", "").startswith("application/json")):
        _warn_http_202_content_type(response)


def _warn_http_202_content_type(response):
    """Issue a warning about the response status code."""
    if "Content-Type" in response.headers:
        content_type = '"{}"'.format(response.headers["Content-Type"])
    else:
        content_type = "not present"
    message = (
        "All HTTP 202 responses returned by Pulp should have a content-type "
        'of "application/json" and include a JSON call report. However, the '
        "Content-Type is {}. Here is the HTTP method, URL and headers from "
        "the request that generated this anomalous response: {} {} {}"
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
    if call_report["error"] is not None:
        raise exceptions.CallReportError(
            "A call report contains an error. Full call report: {}".format(call_report)
        )


def _check_tasks(cfg, tasks, task_errors):
    """Inspect each task's ``error``, ``exception`` and ``traceback`` fields.

    If any of these fields is non-null for any tasks, raise a
    ``TaskReportError``.
    """
    for task in tasks:
        for field in task_errors:
            if task[field] is not None:
                key = "_href" if cfg.pulp_version < Version("3") else "pulp_href"
                msg = "Task report {} contains a {}: {}\nFull task report: {}"
                msg = msg.format(task[key], field, task[field], task)
                raise exceptions.TaskReportError(msg, task)


def _handle_202(cfg, response, pulp_host):
    """Check for an HTTP 202 response and handle it appropriately."""
    if response.status_code == 202:  # "Accepted"
        _check_http_202_content_type(response)
        call_report = response.json()
        tasks = tuple(poll_spawned_tasks(cfg, call_report, pulp_host))
        logger.debug("Task call report: %s", call_report)
        if cfg.pulp_version < Version("3"):
            _check_call_report(call_report)
            _check_tasks(cfg, tasks, ("error", "exception", "traceback"))
        else:
            _check_tasks(cfg, tasks, ("error",))


def _walk_pages(cfg, page, pulp_host):
    """Walk through pages, yielding the "results" in each page."""
    client = Client(cfg, json_handler, pulp_host=pulp_host)
    while True:
        yield page["results"]
        if page["next"]:
            page = client.get(page["next"])
        else:
            break


def echo_handler(client, response):
    """Immediately return ``response``."""
    logger.debug("response status: %s", response.status_code)
    return response


def code_handler(client, response):
    """Check the response status code, and return the response.

    Unlike :meth:`safe_handler`, this method doesn't wait for asynchronous
    tasks to complete if ``response`` has an HTTP 202 status code.

    :raises: ``requests.exceptions.HTTPError`` if the response status code is
        in the 4XX or 5XX range.
    """
    response.raise_for_status()
    logger.debug("response status: %s", response.status_code)
    return response


def safe_handler(client, response):
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
    logger.debug("response status: %s", response.status_code)
    _handle_202(client._cfg, response, client.pulp_host)
    return response


def json_handler(client, response):
    """Like ``safe_handler``, but also return a JSON-decoded response body.

    Do what :func:`pulp_smash.api.safe_handler` does. In addition, decode the
    response body as JSON and return the result.
    """
    response.raise_for_status()
    logger.debug("response status: %s", response.status_code)
    if response.status_code == 204:
        return response
    _handle_202(client._cfg, response, client.pulp_host)
    return response.json()


def page_handler(client, response):
    """Call :meth:`json_handler`, optionally collect results, and return.

    Do the following:

    1. If ``response`` has an HTTP No Content (204) `status code`_, return
       ``response``.
    2. Call :meth:`json_handler`.
    3. If the response appears to be paginated, walk through each page of
       results, and collect them into a single list. Otherwise, do nothing.
       Return either the list of results or the single decoded response.

    :raises: ``ValueError`` if the target Pulp application under test is older
        than version 3 or at least version 4.

    .. _status code: https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
    """
    check_pulp3_restriction(client)
    maybe_page = json_handler(client, response)
    if not isinstance(maybe_page, dict):
        return maybe_page  # HTTP 204 No Content
    if "results" not in maybe_page:
        return maybe_page  # Content isn't a page.

    collected_results = []
    for result in _walk_pages(client._cfg, maybe_page, client.pulp_host):
        collected_results.extend(result)
    logger.debug("paginated %s result pages", len(collected_results))
    return collected_results


def task_handler(client, response):
    """Wait for tasks to complete and then collect resources.

    Do the following:

    1. Call :meth:`json_handler` to handle 202 and get call_report.
    2. Raise error if response is not a task.
    3. Re-read the task by its _href to get the final state and metadata.
    4. Return the task's created or updated resource or task final state.

    :raises: ``ValueError`` if the target Pulp application under test is older
        than version 3 or at least version 4.

    Usage examples:

    Create a distribution using meth:`json_handler`::

        client = Client(cfg, api.json_handler)
        spawned_task = client.post(DISTRIBUTION_PATH, body)
        # json_handler returns the task call report not the created entity
        spawned_task == {'task': ...}
        # to have the distribution it is needed to get the task's resources

    Create a distribution using meth:`task_handler`::

        client = Client(cfg, api.task_handler)
        distribution = client.post(DISTRIBUTION_PATH, body)
        # task_handler resolves the created entity and returns its data
        distribution == {'_href': ..., 'base_path': ...}

    Having an existent client it is possible to use the shortcut::

       client.using_handler(api.task_handler).post(DISTRIBUTION_PATH, body)

    """
    check_pulp3_restriction(client)
    # JSON handler takes care of pooling tasks until it is done
    # If task errored then json_handler will raise the error
    response_dict = json_handler(client, response)
    if "task" not in response_dict:
        raise exceptions.CallReportError(
            "Response does not contains a task call_report: {}".format(response_dict)
        )

    # Get the final state of the done task
    done_task = client.using_handler(json_handler).get(response_dict["task"])

    if response.request.method == "POST":
        # Task might have created new resources
        if "created_resources" in done_task:
            created = done_task["created_resources"]
            logger.debug("Task created resources: %s", created)
            if len(created) == 1:  # Single resource href
                return client.using_handler(json_handler).get(created[0])
            if len(created) > 1:  # Multiple resource hrefs
                return [
                    client.using_handler(json_handler).get(resource_href)
                    for resource_href in created
                ]
        else:
            return []

    if response.request.method in ["PUT", "PATCH"]:
        # Task might have updated resource so re-read and return it back
        logger.debug("Task updated resource: %s", response.request.url)
        return client.using_handler(json_handler).get(response.request.url)

    # response.request.method is one of ['DELETE', 'GET', 'HEAD', 'OPTION']
    # Returns the final state of the done task
    logger.debug("Task finished: %s", done_task)
    return done_task


def smart_handler(client, response):
    """Decides which handler to call based on response content.

    Do the following:

    1. Pass response through safe_handler to handle 202 and raise_for_status.
    2. Return the response if it is not Pulp 3.
    3. Return the response if it is not application/json type.
    4. Pass response through task_handler if is JSON 202 with 'task'.
    5. Pass response through page_handler if is JSON but not 202 with 'task'.
    """
    # safe_handler Will raise_for_Status, handle 202 and pool tasks
    response = safe_handler(client, response)

    try:
        check_pulp3_restriction(client)
    except ValueError:
        # If pulp is not 3+ return the result of safe_handler by default
        return response

    if response.headers.get("Content-Type") != "application/json":
        # Not a valid JSON, return pure response
        logger.debug("Response is not JSON")
        return response

    # We got JSON is that a task call report?
    if response.status_code == 202 and "task" in response.json():
        logger.debug("Response is a task")
        return task_handler(client, response)

    # Its JSON, it is not a Task, default to page_handler
    logger.debug("Response is a JSON")
    return page_handler(client, response)


class Client:
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
    >>> def response_handler(client, response):
    ...     response.raise_for_status()
    ...     return response.json()
    >>> client = Client(get_config(), response_handler=response_handler)
    >>> response = client.post('/pulp/api/v2/users/', {'login': 'Alice'})
    >>> response = client.get(response['_href'])
    >>> print(response)

    Pulp Smash ships with several response handlers. In order of increasing
    complexity, see:

    * :func:`pulp_smash.api.echo_handler`
    * :func:`pulp_smash.api.code_handler`
    * :func:`pulp_smash.api.safe_handler`
    * :func:`pulp_smash.api.json_handler`
    * :func:`pulp_smash.api.page_handler`
    * :func:`pulp_smash.api.task_handler`
    * :func:`pulp_smash.api.smart_handler`

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
    ...     pulp_version='1!0',
    ...     pulp_selinux_enabled=True,
    ...     hosts=[
    ...         config.PulpHost(
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

    As shown above, an argument that's passed to one of this class' methods is
    passed to the corresponding Requests method. And an argument that's set in
    ``requests_kwargs`` is passed to Requests during every call.

    The ``url`` argument is special. When making an HTTP request with Requests,
    an absolute URL is required. But when making an HTTP request with one of
    this class' methods, either an absolute or a relative URL may be passed. If
    a relative URL is passed, it's joined to this class' default URL like so:

    >>> urljoin(self.request_kwargs['url'], passed_in_url)

    This allows one to easily use the hrefs returned by Pulp in constructing
    new requests.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp app.
    :param response_handler: A callback function, invoked after each request is
        made. Must accept two arguments: a
        :class:`pulp_smash.config.PulpSmashConfig` object, and a
        ``requests.Response`` object. Defaults to :func:`smart_handler`.
    :param request_kwargs: A dict of parameters to send with each request. This
        dict is merged into the default dict of parameters that's sent with
        each request.
    :param pulp_smash.config.PulpHost pulp_host: The host with which to
        communicate. Defaults to the first host that fulfills the "api" role.

    **Supplementary information on writing response handlers.**

    This class accepts a :class:`pulp_smash.config.PulpSmashConfig` parameter.
    This object may be accessed via the ``_cfg`` attribute. This attribute
    should be used sparingly, as careless accesses can be an easy way to
    inadverdently create bugs. For example, if given the choice between calling
    ``self._cfg.get_request_kwargs()`` or referencing ``self.request_kwargs``,
    reference the latter. To explain why, consider this scenario:

    >>> from pulp_smash import api, config
    >>> client = api.Client(config.get_config())
    >>> client.request_kwargs['verify'] == '~/Documents/my.crt'
    >>> client.get('https://example.com')

    The API client has been told to use an SSL certificate for verification.
    Yet if the client uses ``self._cfg.get_requests_kwargs()`` when making an
    HTTP GET call, the SSL certificate won't be used.

    If this attribute is so problematic, why does it exist? It exists so that
    each API client may share context with its response handler. For example, a
    response handler might need to know which version of Pulp it is
    communicating with:

    >>> def example_handler(client, response):
    ...     if client._cfg.pulp_version < Version('3'):
    ...         return pulp_2_procedure(response)
    ...     else:
    ...         return pulp_3_procedure(response)

    However, this same logic could also be implemented by calling
    :func:`pulp_smash.config.get_config`:

    >>> def example_handler(client, response):
    ...     if config.get_config().pulp_version < Version('3'):
    ...         return pulp_2_procedure(response)
    ...     else:
    ...         return pulp_3_procedure(response)

    Given this, why lug around a :class:`pulp_smash.config.PulpSmashConfig`
    object? This is done because it is fundamentally correct for a response
    handler to learn about its calling API client's state by accessing the
    calling API client, and it is fundamentally incorrect for a response
    handler to learn about its calling API client's state by accessing a global
    cache. To illustrate, consider one possible failure scenario:

    1. No settings file exists at any of the default load paths, e.g.
       ``~/.config/pulp_smash/settings.json``.
    2. An API client is created by reading a non-default configuration file.
    3. The API client makes a request, and a response handler is invoked to
       handle the response.
    4. The response handler needs to learn which version of Pulp is being
       targeted.

       * If it invokes :func:`pulp_smash.config.get_config`, no configuration
         file will be found, and an exception will be raised.
       * If it accesses the calling API client, it will find what it needs.

    Letting a response handler access its calling API client prevents incorrect
    behaviour in other scenarios too, such as when working with multi-threaded
    code.

    **Supplementary information on method signatures.**

    `requests.post`_ has the following signature::

        requests.post(url, data=None, json=None, **kwargs)

    However, :func:`post` has a different signature. Why? Pulp supports only
    JSON for most of its API endpoints, so it makes sense for us to demote
    ``data`` to being a regular kwarg and list ``json`` as the one and only
    positional argument.

    We make ``json`` a positional argument for :func:`post`, :func:`put`, and
    :func:`patch`, but not the other methods. Why? Because HTTP OPTIONS, GET,
    HEAD and DELETE **must not** have bodies. This is stated by the HTTP/1.1
    specification, and network intermediaries such as caches are at liberty to
    drop such bodies.

    Why is a sentinel object used in several function signatures? Imagine the
    following scenario: a user provides a default JSON payload in
    ``self.request_kwargs``, but they want to skip sending that payload for
    just one request. How can they do that?  With ``client.post(url,
    json=None)``.

    .. _Pulp: http://www.pulpproject.org/
    .. _Requests: http://docs.python-requests.org/en/latest/
    .. _requests.post:
    http://docs.python-requests.org/en/master/api/#requests.post
    """

    def __init__(self, cfg, response_handler=None, request_kwargs=None, pulp_host=None):
        """Initialize this object with needed instance attributes."""
        self._cfg = cfg
        self.response_handler = response_handler or smart_handler
        self.pulp_host = pulp_host or self._cfg.get_hosts("api")[0]
        self.request_kwargs = self._cfg.get_requests_kwargs(self.pulp_host)
        self.request_kwargs["url"] = self._cfg.get_base_url(self.pulp_host)
        if request_kwargs:
            self.request_kwargs.update(request_kwargs)
        self._using_handler_cache = {}
        logger.debug("New %s", self)

    def __str__(self):
        """Client str representation."""
        client_spec = {
            "response_handler": self.response_handler,
            "host": self.pulp_host,
            "cfg": repr(self._cfg),
        }
        return "<api.Client(%s)>" % client_spec

    def using_handler(self, response_handler):
        """Return a copy this same client changing specific handler dependency.

        This method clones and injects a new handler dependency in to the
        existing client instance and then returns it.

        This method is offered just as a 'syntax-sugar' for::

          from pulp_smash import api, config

          def function(client):
              # This function needs to use a different handler
              other_client = api.Client(config.get_config(), other_handler)
              other_client.get(url)

        with this method the above can be done in fewer lines::

            def function(client):  # already receives a client here
                client.using_handler(other_handler).get(url)

        """
        logger.debug("Switching %s to %s", self.response_handler, response_handler)
        try:
            existing_client = self._using_handler_cache[response_handler]
            logger.debug("Reusing Existing Client: %s", existing_client)
            return existing_client
        except KeyError:  # EAFP
            new = copy.copy(self)
            new.response_handler = response_handler
            self._using_handler_cache[response_handler] = new
            logger.debug("Creating a new copy of Client %s", new)
            return new

    def delete(self, url, **kwargs):
        """Send an HTTP DELETE request."""
        return self.request("DELETE", url, **kwargs)

    def get(self, url, **kwargs):
        """Send an HTTP GET request."""
        return self.request("GET", url, **kwargs)

    def head(self, url, **kwargs):
        """Send an HTTP HEAD request."""
        return self.request("HEAD", url, **kwargs)

    def options(self, url, **kwargs):
        """Send an HTTP OPTIONS request."""
        return self.request("OPTIONS", url, **kwargs)

    def patch(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP PATCH request."""
        if json is _SENTINEL:
            return self.request("PATCH", url, **kwargs)
        return self.request("PATCH", url, json=json, **kwargs)

    def post(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP POST request."""
        if json is _SENTINEL:
            return self.request("POST", url, **kwargs)
        return self.request("POST", url, json=json, **kwargs)

    def put(self, url, json=_SENTINEL, **kwargs):
        """Send an HTTP PUT request."""
        if json is _SENTINEL:
            return self.request("PUT", url, **kwargs)
        return self.request("PUT", url, json=json, **kwargs)

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
        intended_host = self.pulp_host.hostname
        request_kwargs = self.request_kwargs.copy()
        request_kwargs["url"] = urljoin(request_kwargs["url"], url)
        request_kwargs.update(kwargs)
        actual_host = urlparse(request_kwargs["url"]).hostname
        if intended_host != actual_host:
            warnings.warn(
                "This client should be used to communicate with {0}, but a "
                "request is being made to {1}. The request will be made, but "
                "beware that information intended for {0} (such as "
                "authentication tokens) may now be sent to {1}. Here's the "
                "list of options being sent with this request: {2}".format(
                    intended_host, actual_host, request_kwargs
                ),
                RuntimeWarning,
            )
        logger.debug("Making a %s request with %s", method, request_kwargs)
        response = self.response_handler(self, requests.request(method, **request_kwargs))
        logger.debug("Finished %s request with response: %s", method, response)
        return response


def poll_spawned_tasks(cfg, call_report, pulp_host=None):
    """Recursively wait for spawned tasks to complete. Yield response bodies.

    Recursively wait for each of the spawned tasks listed in the given `call
    report`_ to complete. For each task that completes, yield a response body
    representing that task's final state.

    :param cfg: A :class:`pulp_smash.config.PulpSmashConfig` object.
    :param call_report: A dict-like object with a `call report`_ structure.
    :param pulp_host: The host to poll. If ``None``, a host will automatically
        be selected by :class:`Client`.
    :returns: A generator yielding task bodies.
    :raises: Same as :meth:`poll_task`.

    .. _call report:
        http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report
    """
    if cfg.pulp_version < Version("3"):
        hrefs = (task["_href"] for task in call_report["spawned_tasks"])
    else:
        hrefs = [call_report["task"]]
    for href in hrefs:
        for final_task_state in poll_task(cfg, href, pulp_host):
            yield final_task_state


def _get_sleep_time(cfg):
    """Returns the default waiting time for polling tasks.

    :param cfg: A :class:`pulp_smash.config.PulpSmashConfig` object.
    """
    if cfg.pulp_version < Version("3"):
        return 2
    return 0.3


def poll_task(cfg, href, pulp_host=None):
    """Wait for a task and its children to complete. Yield response bodies.

    Poll the task at ``href``, waiting for the task to complete. When a
    response is received indicating that the task is complete, yield that
    response body and recursively poll each child task.

    :param cfg: A :class:`pulp_smash.config.PulpSmashConfig` object.
    :param href: The path to a task you'd like to monitor recursively.
    :param pulp_host: The host to poll. If ``None``, a host will automatically
        be selected by :class:`Client`.
    :returns: An generator yielding response bodies.
    :raises pulp_smash.exceptions.TaskTimedOutError: If a task takes too
        long to complete.
    """
    # Read the timeout in seconds from the cfg, and divide by the sleep_time
    # to see how many times we query Pulp.
    # An example: Assuming timeout = 1800s, and sleep_time = 0.3s
    # 1800s/0.3s = 6000

    sleep_time = _get_sleep_time(cfg)
    poll_limit = int(cfg.timeout / sleep_time)
    poll_counter = 0
    json_client = Client(cfg, json_handler, pulp_host=pulp_host)
    logger.debug("Polling task %s with poll_limit %s", href, poll_limit)
    while True:
        task = json_client.get(href)
        if cfg.pulp_version < Version("3"):
            task_end_states = _TASK_END_STATES
        else:
            task_end_states = _P3_TASK_END_STATES
        if task["state"] in task_end_states:
            # This task has completed. Yield its final state, then recursively
            # iterate through children and yield their final states.
            yield task
            if "spawned_tasks" in task:
                for spawned_task in task["spawned_tasks"]:
                    key = "_href" if cfg.pulp_version < Version("3") else "pulp_href"
                    for descendant_tsk in poll_task(cfg, spawned_task[key], pulp_host):
                        yield descendant_tsk
            break
        poll_counter += 1
        if poll_counter > poll_limit:
            raise exceptions.TaskTimedOutError(
                "Task {} is ongoing after {} polls.".format(href, poll_limit)
            )
        logger.debug("Polling %s progress %s/%s", href, poll_counter, poll_limit)
        sleep(sleep_time)
