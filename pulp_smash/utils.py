# coding=utf-8
"""Utility functions for Pulp tests."""
from __future__ import unicode_literals

import requests
import uuid
import warnings
from functools import wraps
from packaging.version import Version
from pulp_smash.constants import REPOSITORY_PATH, USER_PATH
from time import sleep


_TASK_END_STATES = ('canceled', 'error', 'finished', 'skipped', 'timed out')

# These are all possible values for a bug's "status" field.
#
# These statuses apply to bugs filed at https://pulp.plan.io. They are ordered
# according to an ideal workflow. As of this writing, these is no canonical
# public source for this information. But see:
# http://pulp.readthedocs.org/en/latest/dev-guide/contributing/bugs.html#fixing
_UNTESTABLE_BUGS = frozenset((
    'NEW',  # bug just entered into tracker
    'ASSIGNED',  # bug has been assigned to an engineer
    'POST',  # bug fix is being reviewed by dev ("posted for review")
    'MODIFIED',  # bug fix has been accepted by dev
))
_TESTABLE_BUGS = frozenset((
    'ON_QA',  # bug fix is being reviewed by qe
    'VERIFIED',  # bug fix has been accepted by qe
    'CLOSED - CURRENTRELEASE',
    'CLOSED - DUPLICATE',
    'CLOSED - NOTABUG',
    'CLOSED - WONTFIX',
    'CLOSED - WORKSFORME',
))

# A mapping between bug IDs and bug statuses. Used by `_get_bug_status`.
#
# Bug IDs and statuses should be integers and strings, respectively. Example:
#
#     _BUG_STATUS_CACHE[1356] → 'NEW'
#     _BUG_STATUS_CACHE['1356'] → KeyError
#
_BUG_STATUS_CACHE = {}


class TaskTimedOutException(Exception):
    """Indicates that polling a task timed out."""


class BugStatusUnknownError(Exception):
    """Indicates a bug has a status that Pulp Smash doesn't know about."""


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
        server_config.base_url + REPOSITORY_PATH,
        json=body,
        **server_config.get_requests_kwargs()
    ), responses)


def create_user(server_config, body, responses=None):
    """Create a user. Return the response body.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param body: An object to encode as JSON and pass as the request body.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.

    """
    return handle_response(requests.post(
        server_config.base_url + USER_PATH,
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
        server_config.base_url + href,
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
        server_config.base_url + href + 'importers/',
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
    poll_limit = 10
    poll_counter = 0
    while True:
        response = requests.get(
            server_config.base_url + href,
            **server_config.get_requests_kwargs()
        )
        response.raise_for_status()
        attrs = response.json()
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
        server_config.base_url + href + 'actions/publish/',
        json={'id': distributor_id},
        **server_config.get_requests_kwargs()
    ), responses)


def require(version_string):
    """A decorator for optionally skipping test methods.

    This decorator concisely encapsulates a common pattern for skipping tests.
    It can be used like so:

    >>> from pulp_smash.config import get_config
    >>> from pulp_smash.utils import require
    >>> from unittest import TestCase
    >>> class MyTestCase(TestCase):
    ...
    ...     @classmethod
    ...     def setUpClass(cls):
    ...         cls.cfg = get_config()
    ...
    ...     @require('2.7')  # References `self.cfg`
    ...     def test_foo(self):
    ...         pass  # Add a test for Pulp 2.7+ here.

    Notice that ``cls.cfg`` is assigned to. This is a **requirement**.

    :param version_string: A PEP 440 compatible version string.

    """
    # Running the test suite can take a long time. Let's parse the version
    # string now instead of waiting until the test is running.
    min_version = Version(version_string)

    def plain_decorator(test_method):
        """An argument-less decorator. Accepts the function being wrapped."""
        @wraps(test_method)
        def new_test_method(self, *args, **kwargs):
            """A wrapper around a test method."""
            if self.cfg.version < min_version:
                self.skipTest(
                    'This test requires Pulp {} or later, but Pulp {} is '
                    'being tested. If this seems wrong, try checking the '
                    '"settings" option in the Pulp Smash configuration file.'
                    .format(version_string, self.cfg.version)
                )
            return test_method(self, *args, **kwargs)
        return new_test_method
    return plain_decorator


def sync_repository(server_config, href, responses=None):
    """Sync a repository.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param href: A string. The path to a repository.
    :param responses: Same as :meth:`handle_response`.
    :returns: Same as :meth:`handle_response`.
    :raises: Same as :meth:`handle_response`.

    """
    return handle_response(requests.post(
        server_config.base_url + href + 'actions/sync/',
        json={'override_config': {}},
        **server_config.get_requests_kwargs()
    ), responses)


def _get_bug_status(bug_id):
    """Fetch information about bug ``bug_id`` from https://pulp.plan.io."""
    # Declaring as global right before assignment triggers: `SyntaxWarning:
    # name '_BUG_STATUS_CACHE' is used prior to global declaration`
    global _BUG_STATUS_CACHE  # pylint:disable=global-variable-not-assigned

    # It's rarely a good idea to do type checking in a duck-typed language.
    # However, efficiency dictates we do so here. Without this type check, the
    # following will cause us to talk to the bug tracker twice and store two
    # values in the cache:
    #
    #     _get_bug_status(1356)
    #     _get_bug_status('1356')
    #
    if not isinstance(bug_id, int):
        raise TypeError(
            'Bug IDs should be integers. The given ID, {} is a {}.'
            .format(bug_id, type(bug_id))
        )
    try:
        return _BUG_STATUS_CACHE[bug_id]
    except KeyError:
        pass

    # Get, cache and return bug status.
    response = requests.get(
        'https://pulp.plan.io/issues/{}.json'.format(bug_id)
    )
    response.raise_for_status()
    _BUG_STATUS_CACHE[bug_id] = response.json()['issue']['status']['name']
    return _BUG_STATUS_CACHE[bug_id]


def bug_is_testable(bug_id):
    """Tell the caller whether bug ``bug_id`` should be tested.

    :param bug_id: An integer bug ID, taken from https://pulp.plan.io.
    :returns: ``True`` if the bug is testable, or ``False`` otherwise.
    :raises: ``TypeError`` if ``bug_id`` is not an integer.
    :raises pulp_smash.utils.BugStatusUnknownError: If the bug has a status
        Pulp Smash does not recognize.
    :raises: BugTrackerUnavailableWarning: If the bug tracker cannot be
        contacted.

    """
    try:
        status = _get_bug_status(bug_id)
    except requests.exceptions.ConnectionError as err:
        message = (
            'Cannot contact the bug tracker. Pulp Smash will assume that the '
            'bug referenced is testable. Error: {}'.format(err)
        )
        warnings.warn(message, RuntimeWarning)
        return True

    if status in _TESTABLE_BUGS:
        return True
    elif status in _UNTESTABLE_BUGS:
        return False
    else:
        # Alternately, we could raise a warning and `return True`.
        raise BugStatusUnknownError(
            'Bug {} has a status of {}. Pulp Smash only knows how to handle '
            'the following statuses: {}'
            .format(bug_id, status, _TESTABLE_BUGS | _UNTESTABLE_BUGS)
        )


def bug_is_untestable(bug_id):
    """Return the inverse of :meth:`bug_is_testable`."""
    return not bug_is_testable(bug_id)
