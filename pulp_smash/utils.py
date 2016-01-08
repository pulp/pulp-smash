# coding=utf-8
"""Utility functions for Pulp tests."""
from __future__ import unicode_literals

import uuid
from time import sleep
try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

import requests

from pulp_smash.constants import REPOSITORY_PATH


_TASK_END_STATES = ('canceled', 'error', 'finished', 'skipped', 'timed out')


class TaskTimedOutException(Exception):
    """Indicates that polling a task timed out."""


def uuid4():
    """Return a random UUID, as a unicode string."""
    return type('')(uuid.uuid4())


def create_repository(server_config, body, responses=None):
    """Create a repository. Return the response body.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param body: An object to encode as JSON and pass as the request body.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.post(
        urljoin(server_config.base_url, REPOSITORY_PATH),
        json=body,
        **server_config.get_requests_kwargs()
    ), responses)


def delete(server_config, href, responses=None):
    """Delete some resource.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to the resource being deleted.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.delete(
        urljoin(server_config.base_url, href),
        **server_config.get_requests_kwargs()
    ), responses)


def get_importers(server_config, href, responses=None):
    """Read a repository's importers.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to a repository.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.get(
        urljoin(server_config.base_url, href + 'importers/'),
        **server_config.get_requests_kwargs()
    ), responses)


def get_distributors(server_config, href, responses=None):
    """Read a repository's distributors.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to a repository.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.get(
        urljoin(server_config.base_url, href + 'distributors/'),
        **server_config.get_requests_kwargs()
    ), responses)


def get(server_config, href, responses=None):
    """Get a document from an HTTP API.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to a document.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.get(
        urljoin(server_config.base_url, href),
        **server_config.get_requests_kwargs()
    ), responses)


def handle_response(response, responses=None):
    """Optionally record ``response``, verify its status code, and decode body.

    :param response: An object returned by ``requests.request`` or similar.
    :param responses: A list, or some other object with the ``append`` method.
        If given, raw server responses are appended to this object.
    :returns: The JSON-decoded body of the ``response``.
    :raises: ``requests.exceptions.HTTPError`` if ``response`` has an HTTP 3XX
        or 4XX status code.
    """
    if responses is not None:
        responses.append(response)
    response.raise_for_status()
    return response.json()


def poll_spawned_tasks(server_config, call_report):
    """Recursively wait for spawned tasks to complete. Yield response bodies.

    Recursively wait for each of the spawned tasks listed in the given `call
    report`_ to complete. For each task that completes, yield a response body
    representing that task's final state.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param call_report: A dict-like object with a `call report`_ structure.
    :returns: A generator yielding task bodies.
    :raises: Same as :meth:`poll_task`.

    .. _call report:
        http://pulp.readthedocs.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report
    """
    hrefs = (task['_href'] for task in call_report['spawned_tasks'])
    for href in hrefs:
        for final_task_state in poll_task(server_config, href):
            yield final_task_state


def poll_task(server_config, href):
    """Wait for a task and its children to complete. Yield response bodies.

    Poll the task at ``href``, waiting for the task to complete. When a
    response is received indicating that the task is complete, yield that
    response body and recursively poll each child task.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: The path to a task you'd like to monitor recursively.
    :returns: An generator yielding response bodies.
    :raises pulp_smash.utils.TaskTimedOutException: If a task takes too long to
        complete.
    """
    poll_limit = 24  # 24 * 5s == 120s
    poll_counter = 0
    while True:
        attrs = get(server_config, href)
        if attrs['state'] in _TASK_END_STATES:
            yield attrs
            for spawned_task in attrs['spawned_tasks']:
                yield poll_task(server_config, spawned_task['_href'])
            break
        poll_counter += 1
        if poll_counter > poll_limit:
            raise TaskTimedOutException(
                'Task {} is ongoing after {} polls.'.format(href, poll_limit)
            )
        # This approach is dumb, in that we don't account for time spent
        # waiting for the Pulp server to respond to us.
        sleep(5)


def publish_repository(server_config, href, distributor_id, responses=None):
    """Publish a repository.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to the repository to which a distributor
        shall be added.
    :param distributor_id: The ID of the distributor performing the publish.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.post(
        urljoin(server_config.base_url, href + 'actions/publish/'),
        json={'id': distributor_id},
        **server_config.get_requests_kwargs()
    ), responses)


def sync_repository(server_config, href, responses=None):
    """Sync a repository.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to a repository.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.
    """
    return handle_response(requests.post(
        urljoin(server_config.base_url, href + 'actions/sync/'),
        json={'override_config': {}},
        **server_config.get_requests_kwargs()
    ), responses)
