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

from pulp_smash import cli, exceptions


_TASK_END_STATES = ('canceled', 'error', 'finished', 'skipped', 'timed out')


def uuid4():
    """Return a random UUID, as a unicode string."""
    return type('')(uuid.uuid4())


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
    :raises pulp_smash.exceptions.TaskTimedOutError: If a task takes too
        long to complete.
    """
    poll_limit = 24  # 24 * 5s == 120s
    poll_counter = 0
    while True:
        response = requests.get(
            urljoin(server_config.base_url, href),
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
            raise exceptions.TaskTimedOutError(
                'Task {} is ongoing after {} polls.'.format(href, poll_limit)
            )
        # This approach is dumb, in that we don't account for time spent
        # waiting for the Pulp server to respond to us.
        sleep(5)


# See design discussion at: https://github.com/PulpQE/pulp-smash/issues/31
def get_broker(server_config):
    """Build an object for managing the target system's AMQP broker.

    Talk to the host named by ``server_config`` and use simple heuristics to
    determine which AMQP broker is installed. If Qpid or RabbitMQ appear to be
    installed, return a :class:`pulp_smash.cli.Service` object for managing
    those services respectively. Otherwise, raise an exception.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        system on which an AMQP broker exists.
    :rtype: pulp_smash.cli.Service
    :raises pulp_smash.exceptions.NoKnownBrokerError: If unable to find any
        AMQP brokers on the target system.
    """
    # On Fedora 23, /usr/sbin and /usr/local/sbin are only added to the $PATH
    # for login shells. (See pathmunge() in /etc/profile.) As a result, logging
    # into a system and executing `which qpidd` and remotely executing `ssh
    # pulp.example.com which qpidd` may return different results.
    client = cli.Client(server_config, cli.echo_handler)
    executables = ('qpidd', 'rabbitmq')  # ordering indicates preference
    for executable in executables:
        command = ('test', '-e', '/usr/sbin/' + executable)
        if client.run(command).returncode == 0:
            return cli.Service(server_config, executable)
    raise exceptions.NoKnownBrokerError(
        'Unable to determine the AMQP broker used by {}. It does not appear '
        'to be any of {}.'
        .format(server_config.base_url, executables)
    )
