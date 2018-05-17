# coding=utf-8
"""Tools for managing information about hosts under test.

Pulp Smash needs to know about the Pulp application under test and the hosts
that comprise that application. For example, it might need to know which
username and password to use when communicating with a Pulp application, or it
might need to know which host is hosting the squid service, if any. This module
eases the task of managing that information.
"""
import collections
import itertools
import json
import os
import warnings
from copy import deepcopy
from urllib.parse import urlunsplit

import jsonschema
from packaging.version import Version
from xdg import BaseDirectory

from pulp_smash import exceptions


# `get_config` uses this as a cache. It is intentionally a global. This design
# lets us do interesting things like flush the cache at run time or completely
# avoid a config file by fetching values from the UI.
_CONFIG = None

REQUIRED_ROLES = {
    'amqp broker',
    'api',
    'mongod',
    'pulp celerybeat',
    'pulp resource manager',
    'pulp workers',
    'shell',
}
"""The set of roles that must be present in a functional Pulp application."""

OPTIONAL_ROLES = {
    'pulp cli',
    'squid',
}
"""Additional roles that can be present in a Pulp application."""

ROLES = REQUIRED_ROLES.union(OPTIONAL_ROLES)
"""The set of all roles that may be present in a Pulp application."""

AMQP_SERVICES = {'qpidd', 'rabbitmq'}
"""The set of services that can fulfill the ``amqp broker`` role."""

CONFIG_JSON_SCHEMA = {
    'additionalProperties': False,
    'required': ['pulp', 'hosts'],
    'type': 'object',
    'properties': {
        'pulp': {
            'additionalProperties': False,
            'required': ['auth', 'version'],
            'type': 'object',
            'properties': {
                'auth': {'type': 'array', 'maxItems': 2, 'minItems': 2},
                'version': {'type': 'string'},
                'selinux enabled': {'type': 'boolean'},
            }
        },
        'hosts': {
            'type': 'array',
            'minItems': 1,
            'items': {'$ref': '#/definitions/host'},
        }
    },
    'definitions': {
        'host': {
            'additionalProperties': False,
            'required': ['hostname', 'roles'],
            'type': 'object',
            'properties': {
                'hostname': {
                    'type': 'string',
                    'format': 'hostname',
                },
                'roles': {
                    'additionalProperties': False,
                    'required': ['shell'],
                    'type': 'object',
                    'properties': {
                        'amqp broker': {
                            'required': ['service'],
                            'type': 'object',
                            'properties': {
                                'service': {
                                    'enum': list(AMQP_SERVICES),
                                    'type': 'string',
                                },
                            }
                        },
                        'api': {
                            'required': ['scheme'],
                            'type': 'object',
                            'properties': {
                                'port': {
                                    'type': 'integer',
                                    'minimum': 0,
                                    'maximum': 65535,
                                },
                                'scheme': {
                                    'enum': ['http', 'https'],
                                    'type': 'string',
                                },
                                'verify': {
                                    'type': ['boolean', 'string'],
                                },
                            }
                        },
                        'mongod': {
                            'type': 'object',
                        },
                        'pulp cli': {
                            'type': 'object',
                        },
                        'pulp celerybeat': {
                            'type': 'object',
                        },
                        'pulp resource manager': {
                            'type': 'object',
                        },
                        'pulp workers': {
                            'type': 'object',
                        },
                        'shell': {
                            'type': 'object',
                            'properties': {
                                'transport': {
                                    'enum': ['local', 'ssh'],
                                    'type': 'string',
                                }
                            }
                        },
                        'squid': {
                            'type': 'object',
                        },
                    }
                }
            }
        }
    },
}
"""The schema for Pulp Smash's configuration file."""


def _public_attrs(obj):
    """Return a copy of the public elements in ``vars(obj)``."""
    return {
        key: val for key, val in vars(obj).copy().items()
        if not key.startswith('_')
    }


def get_config():
    """Return a copy of the global ``PulpSmashConfig`` object.

    This method makes use of a cache. If the cache is empty, the configuration
    file is parsed and the cache is populated. Otherwise, a copy of the cached
    configuration object is returned.

    :returns: A copy of the global server configuration object.
    :rtype: pulp_smash.config.PulpSmashConfig
    """
    global _CONFIG  # pylint:disable=global-statement
    if _CONFIG is None:
        _CONFIG = PulpSmashConfig.load()
    return deepcopy(_CONFIG)


def validate_config(config_dict):
    """Validate an in-memory configuration file.

    Given an in-memory configuration file, verify its sanity by validating it
    against a schema and performing several semantic checks.

    :param config_dict: A dictionary returned by ``json.load`` or
        ``json.loads`` after loading the config file.
    :raises pulp_smash.exceptions.ConfigValidationError: If the any validation
        error is found.
    """
    validator_cls = jsonschema.validators.validator_for(CONFIG_JSON_SCHEMA)
    validator = validator_cls(
        schema=CONFIG_JSON_SCHEMA, format_checker=jsonschema.FormatChecker())
    validator.check_schema(CONFIG_JSON_SCHEMA)
    messages = []

    if not validator.is_valid(config_dict):
        for error in validator.iter_errors(config_dict):
            # jsonschema returns messages where the first letter is uppercase,
            # make sure to lower the first letter case to fit better on our
            # message.
            error_message = error.message[:1].lower() + error.message[1:]
            if error.relative_path:
                config_path = '[{}]'.format(
                    ']['.join([repr(i) for i in error.relative_path])
                )
            else:
                config_path = ''
            messages.append(
                'Failed to validate config{} because {}.'.format(
                    config_path,
                    error_message,
                )
            )
    if messages:
        raise exceptions.ConfigValidationError(messages)

    # Now that the schema is valid, let's check if all the REQUIRED_ROLES are
    # defined
    config_roles = set(itertools.chain(*[
        list(host['roles'].keys()) for host in config_dict['hosts']]))
    if not REQUIRED_ROLES.issubset(config_roles):
        raise exceptions.ConfigValidationError([
            'The following roles are missing: {}'.format(
                ', '.join(sorted(REQUIRED_ROLES.difference(config_roles)))
            )
        ])


# Representation of a host and its roles."""
PulpHost = collections.namedtuple('PulpHost', 'hostname roles')


class PulpSmashConfig():
    """Information about a Pulp application.

    This object stores information about Pulp application and its constituent
    hosts. A single Pulp application may have its services spread across
    several hosts. For example, one host might run Qpid, another might run
    MongoDB, and so on. Here's how to model a multi-host deployment where
    Apache runs on one host, and the remaining components run on another host:

    >>> import requests
    >>> from pulp_smash.config import PulpSmashConfig
    >>> cfg = PulpSmashConfig(
    ...     pulp_auth=('username', 'password'),
    ...     pulp_version='2.12.2',
    ...     pulp_selinux_enabled=True,
    ...     hosts=[
    ...         PulpHost(
    ...             hostname='pulp1.example.com',
    ...             roles={'api': {'scheme': 'https'}},
    ...         ),
    ...         PulpHost(
    ...             hostname='pulp.example.com',
    ...             roles={
    ...                 'amqp broker': {'service': 'qpidd'},
    ...                 'mongod': {},
    ...                 'pulp celerybeat': {},
    ...                 'pulp resource manager': {},
    ...                 'pulp workers': {},
    ...                 'shell': {'transport': 'ssh'},
    ...             },
    ...         )
    ...     ]
    ... )

    In the simplest case, all of the services that comprise a Pulp applicaiton
    run on a single host. Here's an example of how this object might model a
    single-host deployment:

    >>> import requests
    >>> from pulp_smash.config import PulpSmashConfig
    >>> cfg = PulpSmashConfig(
    ...     pulp_auth=('username', 'password'),
    ...     pulp_version='2.12.2',
    ...     pulp_selinux_enabled=True,
    ...     hosts=[
    ...         PulpHost(
    ...             hostname='pulp.example.com',
    ...             roles={
    ...                 'amqp broker': {'service': 'qpidd'},
    ...                 'api': {'scheme': 'https'},
    ...                 'mongod': {},
    ...                 'pulp cli': {},
    ...                 'pulp celerybeat': {},
    ...                 'pulp resource manager': {},
    ...                 'pulp workers': {},
    ...                 'shell': {'transport': 'ssh'},
    ...             },
    ...         )
    ...     ]
    ... )

    In the simplest case, Pulp Smash's configuration file resides at
    ``~/.config/pulp_smash/settings.json``. However, there are several ways to
    alter this path. Pulp Smash obeys the `XDG Base Directory Specification`_.
    In addition, Pulp Smash responds to the ``PULP_SMASH_CONFIG_FILE``
    environment variable. This variable is a relative path, and it defaults to
    ``settings.json``.

    Configuration files contain JSON data structured in a way that resembles
    what is accepted by this class's constructor. For exact details on the
    structure of configuration files, see
    :data:`pulp_smash.config.CONFIG_JSON_SCHEMA`.

    :param pulp_auth: A two-tuple. Credentials to use when communicating with
        the server. For example: ``('username', 'password')``.
    :param pulp_version: A string, such as '1.2' or '0.8.rc3'. If you are
        unsure what to pass, consider passing '1!0' (epoch 1, version 0). Must
        be compatible with the `packaging`_ library's
        ``packaging.version.Version`` class.
    :param pulp_selinux_enabled: A boolean. Determines whether selinux tests
        are enabled.
    :param hosts: A list of the hosts comprising a Pulp application. Each
        element of the list should be a :class:`pulp_smash.config.PulpHost`
        object.

    .. _packaging: https://packaging.pypa.io/en/latest/
    .. _XDG Base Directory Specification:
        http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
    """

    def __init__(
            self, pulp_auth, pulp_version, pulp_selinux_enabled, *, hosts):
        """Initialize this object with needed instance attributes."""
        self.pulp_auth = pulp_auth
        self.pulp_version = Version(pulp_version)
        self.pulp_selinux_enabled = pulp_selinux_enabled
        self.hosts = hosts

    def __repr__(self):
        """Create string representation of the object."""
        attrs = _public_attrs(self)
        attrs['pulp_version'] = str(attrs['pulp_version'])
        str_kwargs = ', '.join(
            '{}={}'.format(key, repr(value)) for key, value in attrs.items()
        )
        return '{}({})'.format(type(self).__name__, str_kwargs)

    def get_hosts(self, role):
        """Return a list of hosts fulfilling the given role.

        :param role: The role to filter the available hosts, see
            `pulp_smash.config.ROLES` for more information.
        """
        if role not in ROLES:
            raise ValueError(
                'The given role, {}, is not recognized. Valid roles are: {}'
                .format(role, ROLES)
            )
        return [host for host in self.hosts if role in host.roles]

    @staticmethod
    def get_services(roles):
        """Translate role names to init system service names."""
        services = []
        for role in roles:
            if role == 'amqp broker':
                service = roles[role].get('service')
                if service in AMQP_SERVICES:
                    services.append(service)
            elif role == 'api':
                services.append('httpd')
            elif role in (
                    'pulp celerybeat',
                    'pulp resource manager',
                    'pulp workers',
            ):
                services.append(role.replace(' ', '_'))
            elif role in ('mongod', 'squid'):
                services.append(role)
            else:
                continue
        return set(services)

    def get_base_url(self, pulp_host=None):
        """Generate the base URL for a given ``pulp_host``.

        :param pulp_smash.config.PulpHost pulp_host: One of the hosts that
            comprises a Pulp application. Defaults to the first host with the
            ``api`` role.
        """
        if pulp_host is None:
            pulp_host = self.get_hosts('api')[0]
        scheme = pulp_host.roles['api']['scheme']
        netloc = pulp_host.hostname
        try:
            netloc += ':' + str(pulp_host.roles['api']['port'])
        except KeyError:
            pass
        return urlunsplit((scheme, netloc, '', '', ''))

    def get_requests_kwargs(self, pulp_host=None):
        """Get kwargs for use by the Requests functions.

        This method returns a dict of attributes that can be unpacked and used
        as kwargs via the ``**`` operator. For example:

        >>> cfg = PulpSmashConfig.load()
        >>> requests.get(cfg.get_base_url() + '…', **cfg.get_requests_kwargs())

        This method is useful because client code may not know which attributes
        should be passed from a ``PulpSmashConfig`` object to Requests.
        Consider that the example above could also be written like this:

        >>> cfg = PulpSmashConfig.load()
        >>> requests.get(
        ...     cfg.get_base_url() + '…',
        ...     auth=tuple(cfg.pulp_auth),
        ...     verify=cfg.get_hosts('api')[0].roles['api']['verify'],
        ... )

        But this latter approach is more fragile. The user must remember to get
        a host with api role to check for the verify config, then convert
        ``pulp_auth`` config to a tuple, and it will require maintenance if
        ``cfg`` gains or loses attributes.
        """
        if not pulp_host:
            pulp_host = self.get_hosts('api')[0]
        kwargs = deepcopy(pulp_host.roles['api'])
        kwargs['auth'] = tuple(self.pulp_auth)
        for key in ('port', 'scheme'):
            kwargs.pop(key, None)
        return kwargs

    @classmethod
    def load(cls, xdg_subdir=None, config_file=None):
        """Load a configuration file from disk.

        :param xdg_subdir: Passed to :meth:`get_load_path`.
        :param config_file: Passed to :meth:`get_load_path`.
        :returns: A new :class:`pulp_smash.config.PulpSmashConfig` object. The
            current object is not modified by this method.
        :rtype: PulpSmashConfig
        """
        # Load JSON from disk.
        path = cls.get_load_path(xdg_subdir, config_file)
        with open(path) as handle:
            loaded_config = json.load(handle)

        # Make arguments.
        pulp = loaded_config.get('pulp', {})
        pulp_auth = pulp.get('auth', ['admin', 'admin'])
        pulp_version = pulp.get('version', '1!0')
        pulp_selinux_enabled = pulp.get('selinux enabled', True)
        if 'systems' in loaded_config:
            warnings.warn(
                (
                    'The Pulp Smash configuration file should use a key named '
                    '"hosts," not "systems." Please update accordingly, and '
                    'validate the changes with `pulp-smash settings validate`.'
                ),
                DeprecationWarning
            )
            loaded_config['hosts'] = loaded_config.pop('systems')
        hosts = [PulpHost(**host) for host in loaded_config.get('hosts', [])]

        # Make object.
        return PulpSmashConfig(
            pulp_auth,
            pulp_version,
            pulp_selinux_enabled,
            hosts=hosts,
        )

    @classmethod
    def get_load_path(cls, xdg_subdir=None, config_file=None):
        """Return the path to where a configuration file may be loaded from.

        Search each of the ``$XDG_CONFIG_DIRS`` for a file named
        ``$xdg_subdir/$config_file``.

        :param xdg_subdir: A string. The directory to append to each of the
            ``$XDG_CONFIG_DIRS``. Defaults to ``'pulp_smash'``.
        :param config_file: A string. The name of the settings file. Typically
            defaults to ``'settings.json'``.
        :returns: A string. The path to a configuration file, if one is found.
        :raises pulp_smash.exceptions.ConfigFileNotFoundError: If no
            configuration file is found.
        """
        if xdg_subdir is None:
            xdg_subdir = cls._get_xdg_subdir()
        if config_file is None:
            config_file = cls._get_config_file()

        for dir_ in BaseDirectory.load_config_paths(xdg_subdir):
            path = os.path.join(dir_, config_file)
            if os.path.exists(path):
                return path

        raise exceptions.ConfigFileNotFoundError(
            'Pulp Smash is unable to find a configuration file. The '
            'following (XDG compliant) paths have been searched: '
            ', '.join((
                os.path.join(xdg_config_dir, xdg_subdir, config_file)
                for xdg_config_dir in BaseDirectory.xdg_config_dirs
            ))
        )

    @classmethod
    def get_save_path(cls):
        """Return a path to where a configuration file may be saved.

        Create parent directories if they don't exist.
        """
        return os.path.join(
            BaseDirectory.save_config_path(cls._get_xdg_subdir()),
            cls._get_config_file(),
        )

    @staticmethod
    def _get_xdg_subdir():
        """Return the name (not path!) of this application's subdirectory.

        This name may be appended to ``$XDG_CONFIG_DIRS``, ``$XDG_DATA_DIRS``,
        ``$XDG_DATA_HOME``, and so on. For more, search for "subdir" within the
        `XDG base directory specification
        <https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html>`_.
        """
        return 'pulp_smash'

    @staticmethod
    def _get_config_file():
        """Return the name (not path!) of the Pulp Smash configuration file.

        Defaults to ``settings.json``, but may be overridden by an environment
        variable named ``PULP_SMASH_CONFIG_FILE``.
        """
        return os.environ.get('PULP_SMASH_CONFIG_FILE', 'settings.json')
