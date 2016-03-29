# coding=utf-8
"""Utility functions for Pulp tests.

This module may make use of :mod:`pulp_smash.api` and :mod:`pulp_smash.cli`,
but the reverse should not be done.
"""
from __future__ import unicode_literals

import uuid

import unittest2

from pulp_smash import api, cli, config, exceptions
from pulp_smash.constants import ORPHANS_PATH, PLUGIN_TYPES_PATH, PULP_SERVICES


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
    prefix = '' if is_root(server_config) else 'sudo '
    client.run('mongo pulp_database --eval db.dropDatabase()'.split())
    client.run('sudo -u apache pulp-manage-db'.split())
    client.run((prefix + 'rm -rf /var/lib/pulp/content').split())
    client.run((prefix + 'rm -rf /var/lib/pulp/published').split())

    for service in services:
        service.start()


class BaseAPITestCase(unittest2.TestCase):
    """A class with behaviour that is of use in many API test cases.

    This test case provides set-up and tear-down behaviour that is common to
    many API test cases. It is not necessary to use this class as the parent of
    all API test cases, but it serves well in many cases.
    """

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an iterable of resources to delete.

        The following class attributes are created this method:

        ``cfg``
            A :class:`pulp_smash.config.ServerConfig` object.
        ``resources``
            A set object. If a child class creates some resources that should
            be deleted when the test is complete, the child class should add
            that resource's href to this set.
        """
        cls.cfg = config.get_config()
        cls.resources = set()

    @classmethod
    def tearDownClass(cls):
        """Delete all resources named by ``resources``."""
        client = api.Client(cls.cfg)
        for resource in cls.resources:
            client.delete(resource)
        client.delete(ORPHANS_PATH)


def reset_squid(server_config):
    """Stop Squid, reset its cache directory, and restart it.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: Nothing.
    """
    squid_service = cli.Service(server_config, 'squid')
    squid_service.stop()

    # Clean out the cache directory and reinitialize it.
    client = cli.Client(server_config)
    prefix = '' if is_root(server_config) else 'sudo '
    client.run((prefix + 'rm -rf /var/spool/squid').split())
    client.run((prefix + 'mkdir --context=system_u:object_r:squid_cache_t:s0' +
                ' --mode=750 /var/spool/squid').split())
    client.run((prefix + 'chown squid:squid /var/spool/squid').split())
    client.run((prefix + 'squid -z').split())

    squid_service.start()


def get_plugin_type_ids():
    """Get the ID of each of Pulp's plugins.

    Each Pulp plugin adds one (or more?) content unit type to Pulp. Each of
    these content unit types is identified by a certain unique identifier. For
    example, the `Python type`_ has an ID of ``python_package``.

    :returns: A set of plugin IDs. For example: ``{'ostree',
        'python_package'}``.

    .. _Python type:
       http://pulp-python.readthedocs.org/en/latest/reference/python-type.html
    """
    client = api.Client(config.get_config(), api.json_handler)
    plugin_types = client.get(PLUGIN_TYPES_PATH)
    return {plugin_type['id'] for plugin_type in plugin_types}


def is_root(server_config):
    """Tell if we are root on the target system.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: Either ``True`` or ``False``.
    """
    if cli.Client(server_config).run(('id', '-u')).stdout.strip() == '0':
        return True
    return False
