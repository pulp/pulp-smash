# coding=utf-8
"""Custom exceptions defined by Pulp Smash."""


class BugStatusUnknownError(Exception):
    """We have encountered a bug whose status is unknown to us.

    See :mod:`pulp_smash.selectors` for more information on how bug statuses
    are used.
    """


class BugTPRMissingError(Exception):
    """We have encountered a bug with no "Target Platform Release" field.

    See :mod:`pulp_smash.selectors` for more information.
    """


class CallReportError(Exception):
    """A call report contains an error.

    For more information about pulp's task handling, see
    `Synchronous and Asynchronous Calls`_ and `Task Management`_.

    .. _Synchronous and Asynchronous Calls:
        http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html
    .. _Task Management:
        http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/tasks.html
    """


class ConfigFileNotFoundError(Exception):
    """We cannot find the requested Pulp Smash configuration file.

    See :mod:`pulp_smash.config` for more information on how configuration
    files are handled.
    """


class ConfigFileSectionNotFoundError(Exception):
    """We cannot read the requested Pulp Smash configuration file section.

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


class TaskReportError(Exception):
    """A task contains an error.

    For more information about pulp's task handling, see
    `Synchronous and Asynchronous Calls`_ and `Task Management`_.

    .. _Synchronous and Asynchronous Calls:
        http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html
    .. _Task Management:
        http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/tasks.html
    """


class TaskTimedOutError(Exception):
    """We timed out while polling a task and waiting for it to complete.

    See :func:`pulp_smash.api.poll_spawned_tasks` and
    :func:`pulp_smash.api.poll_task` for more information on how task polling
    is handled.
    """
