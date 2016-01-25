# coding=utf-8
"""Custom exceptions defined by Pulp Smash."""
from __future__ import unicode_literals


class BugStatusUnknownError(Exception):
    """We have encountered a bug whose status is unknown to us.

    See :mod:`pulp_smash.selectors` for more information on how bug statuses
    are used.
    """


class ConfigFileNotFoundError(Exception):
    """We cannot find the requested Pulp Smash configuration file.

    See :mod:`pulp_smash.config` for more information on how configuration
    files are handled.
    """


class NoKnownBrokerError(Exception):
    """We cannot determine the AMQP broker used by a system.

    An "AMQP broker" is a tool such as RabbitMQ or Apache Qpid.
    """


class NoKnownServiceManagerError(Exception):
    """We cannot determine the service manager used by a system.

    A "service manager" is a tool such as ``systemctl`` or ``service``.
    """


class TaskTimedOutException(Exception):
    """We timed out while polling a task and waiting for it to complete.

    See :func:`pulp_smash.utils.poll_spawned_tasks` and
    :func:`pulp_smash.utils.poll_task` for more information on how task polling
    is handled.
    """
