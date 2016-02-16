# coding=utf-8
"""Utility functions for Pulp tests.

This module may make use of :mod:`pulp_smash.api` and :mod:`pulp_smash.cli`,
but the reverse should not be done.
"""
from __future__ import unicode_literals

import uuid

from pulp_smash import cli, exceptions
from pulp_smash.constants import PULP_SERVICES


def uuid4():
    """Return a random UUID, as a unicode string."""
    return type('')(uuid.uuid4())


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


def reset_pulp(server_config):
    """Stop Pulp, reset its database, remove certain files, and start it.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: Nothing.
    """
    services = tuple((
        cli.Service(server_config, service) for service in PULP_SERVICES
    ))
    for service in services:
        service.stop()

    # Reset the database and nuke accumulated files.
    client = cli.Client(server_config)
    prefix = '' if client.run(('id', '-u')).stdout.strip() == '0' else 'sudo '
    client.run('mongo pulp_database --eval db.dropDatabase()'.split())
    client.run('sudo -u apache pulp-manage-db'.split())
    client.run((prefix + 'rm -rf /var/lib/pulp/content/*').split())
    client.run((prefix + 'rm -rf /var/lib/pulp/published/*').split())

    for service in services:
        service.start()
