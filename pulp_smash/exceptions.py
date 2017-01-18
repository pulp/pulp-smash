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


class CalledProcessError(Exception):
    """Indicates a CLI process has a non-zero return code.

    See :meth:`pulp_smash.cli.CompletedProcess` for more information.
    """

    def __init__(self, args, returncode, stdout, stderr):
        """An exceptionally simple constructor.

        Pass all arguments to ``super()``.
        """
        super().__init__(args, returncode, stdout, stderr)

    def __str__(self):
        """Provide a human-friendly string representation of this exception."""
        return (
            'Command {} returned non-zero exit status {}.\n\n'
            'stdout: {}\n\n'
            'stderr: {}'
        ).format(*self.args)


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


class NoKnownPackageManagerError(Exception):
    """We cannot determine the package manager used by a system.

    A "package manager" is a tool such as ``yum`` or ``dnf``.
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

    def __init__(self, msg, task, *args, **kwargs):
        """Require that a task object is defined."""
        super().__init__(msg, task, *args, **kwargs)
        self.task = task


class TaskTimedOutError(Exception):
    """We timed out while polling a task and waiting for it to complete.

    See :func:`pulp_smash.api.poll_spawned_tasks` and
    :func:`pulp_smash.api.poll_task` for more information on how task polling
    is handled.
    """
