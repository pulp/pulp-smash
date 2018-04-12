# coding=utf-8
"""Unit tests for :mod:`pulp_smash.config`."""
import builtins
import itertools
import json
import os
import random
import unittest
from unittest import mock

import xdg

from pulp_smash import config, exceptions, utils

PULP_SMASH_CONFIG = """
{
    "pulp": {
        "auth": ["username", "password"],
        "version": "2.12.1"
    },
    "systems": [
        {
            "hostname": "first.example.com",
            "roles": {
                "amqp broker": {"service": "qpidd"},
                "api": {"port": 1234, "scheme": "https", "verify": true},
                "mongod": {},
                "pulp cli": {},
                "pulp celerybeat": {},
                "pulp resource manager": {},
                "pulp workers": {},
                "shell": {"transport": "local"},
                "squid": {}
            }
        },
        {
            "hostname": "second.example.com",
            "roles": {
                "api": {"port": 2345, "scheme": "https", "verify": false},
                "pulp celerybeat": {},
                "pulp resource manager": {},
                "pulp workers": {},
                "shell": {"transport": "ssh"},
                "squid": {}
            }
        }
    ]
}
"""


OLD_CONFIG = """
{
    "pulp": {
        "base_url": "https://pulp.example.com",
        "auth": ["username", "password"],
        "verify": false,
        "version": "2.12",
        "cli_transport": "ssh"
    }
}
"""


def _gen_attrs():
    """Generate attributes for populating a ``PulpSmashConfig``.

    Example usage: ``PulpSmashConfig(**_gen_attrs())``.

    :returns: A dict. It populates all attributes in a ``PulpSmashConfig``.
    """
    return {
        'pulp_auth': [utils.uuid4() for _ in range(2)],
        'pulp_version': '.'.join(
            type('')(random.randint(1, 150)) for _ in range(4)
        ),
        'systems': [
            config.PulpSystem(
                hostname='pulp.example.com',
                roles={
                    'amqp broker': {'service': 'qpidd'},
                    'api': {
                        'port': random.randint(1, 65535),
                        'scheme': 'https',
                        'verify': True
                    },
                    'mongod': {},
                    'pulp cli': {},
                    'pulp celerybeat': {},
                    'pulp resource manager': {},
                    'pulp workers': {},
                    'shell': {'transport': 'local'},
                    'squid': {}
                }
            )
        ],
    }


class GetConfigTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.config.get_config`."""

    def test_cache_full(self):
        """No config is read from disk if the cache is populated."""
        with mock.patch.object(config, '_CONFIG'):
            with mock.patch.object(config.PulpSmashConfig, 'read') as read:
                config.get_config()
        self.assertEqual(read.call_count, 0)

    def test_cache_empty(self):
        """A config is read from disk if the cache is empty."""
        with mock.patch.object(config, '_CONFIG', None):
            with mock.patch.object(config.PulpSmashConfig, 'read') as read:
                config.get_config()
        self.assertEqual(read.call_count, 1)


class ConvertOldConfigTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.config.convert_old_config`."""

    def test_convert_old_config(self):
        """Assert the conversion works."""
        expected_config = {
            'pulp': {
                'auth': ['username', 'password'],
                'version': '2.12'
            },
            'systems': [
                {
                    'hostname': 'pulp.example.com',
                    'roles': {
                        'amqp broker': {'service': 'qpidd'},
                        'api': {'scheme': 'https', 'verify': False},
                        'mongod': {},
                        'pulp celerybeat': {},
                        'pulp cli': {},
                        'pulp resource manager': {},
                        'pulp workers': {},
                        'shell': {'transport': 'ssh'},
                        'squid': {},
                    }
                }
            ]
        }
        self.assertEqual(
            config.convert_old_config(json.loads(OLD_CONFIG)),
            expected_config
        )


class ValidateConfigTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.config.validate_config`."""

    def test_valid_config(self):
        """A valid config does not raise an exception."""
        self.assertIsNone(
            config.validate_config(json.loads(PULP_SMASH_CONFIG)))

    def test_invalid_config(self):
        """An invalid config raises an exception."""
        config_dict = json.loads(PULP_SMASH_CONFIG)
        config_dict['pulp']['auth'] = []
        config_dict['systems'][0]['hostname'] = ''
        with self.assertRaises(exceptions.ConfigValidationError) as err:
            config.validate_config(config_dict)
        self.assertEqual(sorted(err.exception.error_messages), sorted([
            'Failed to validate config[\'pulp\'][\'auth\'] because [] is too '
            'short.',
            'Failed to validate config[\'systems\'][0][\'hostname\'] because '
            '\'\' is not a \'hostname\'.',
        ]))

    def test_config_missing_roles(self):
        """Missing required roles in config raises an exception."""
        config_dict = json.loads(PULP_SMASH_CONFIG)
        for system in config_dict['systems']:
            system['roles'].pop('api', None)
            system['roles'].pop('pulp workers', None)
        with self.assertRaises(exceptions.ConfigValidationError) as err:
            config.validate_config(config_dict)
        self.assertEqual(
            err.exception.error_messages,
            ['The following roles are missing: api, pulp workers']
        )


class InitTestCase(unittest.TestCase):
    """Test :class:`pulp_smash.config.PulpSmashConfig` instantiation."""

    @classmethod
    def setUpClass(cls):
        """Generate some attributes and use them to instantiate a config."""
        cls.kwargs = _gen_attrs()
        cls.cfg = config.PulpSmashConfig(**cls.kwargs)

    def test_public_attrs(self):
        """Assert that public attributes have correct values."""
        attrs = config._public_attrs(self.cfg)  # pylint:disable=W0212
        attrs['pulp_version'] = type('')(attrs['pulp_version'])
        self.assertEqual(self.kwargs, attrs)

    def test_private_attrs(self):
        """Assert that private attributes have been set."""
        for attr in ('_xdg_config_file', '_xdg_config_dir'):
            with self.subTest(attr):
                self.assertIsNotNone(getattr(self.cfg, attr))


class PulpSmashConfigFileTestCase(unittest.TestCase):
    """Verify the ``PULP_SMASH_CONFIG_FILE`` environment var is respected."""

    def test_var_set(self):
        """Set the environment variable."""
        os_environ = {'PULP_SMASH_CONFIG_FILE': utils.uuid4()}
        with mock.patch.dict(os.environ, os_environ, clear=True):
            cfg = config.PulpSmashConfig()
        self.assertEqual(
            cfg._xdg_config_file,  # pylint:disable=protected-access
            os_environ['PULP_SMASH_CONFIG_FILE']
        )

    def test_var_unset(self):
        """Do not set the environment variable."""
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = config.PulpSmashConfig()
        # pylint:disable=protected-access
        self.assertEqual(cfg._xdg_config_file, 'settings.json')


class ReadTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.config.PulpSmashConfig.read`."""

    def test_read_config_file(self):
        """Ensure Pulp Smash can read the config file."""
        open_ = mock.mock_open(read_data=PULP_SMASH_CONFIG)
        with mock.patch.object(builtins, 'open', open_):
            cfg = config.PulpSmashConfig()
            with mock.patch.object(cfg, 'get_config_file_path'):
                cfg = cfg.read()
        with self.subTest('check pulp_auth'):
            self.assertEqual(cfg.pulp_auth, ['username', 'password'])
        with self.subTest('check pulp_version'):
            self.assertEqual(cfg.pulp_version, config.Version('2.12.1'))
        with self.subTest('check systems'):
            self.assertEqual(
                sorted(cfg.systems),
                sorted([
                    config.PulpSystem(
                        hostname='first.example.com',
                        roles={
                            'amqp broker': {'service': 'qpidd'},
                            'api': {
                                'port': 1234,
                                'scheme': 'https',
                                'verify': True,
                            },
                            'mongod': {},
                            'pulp cli': {},
                            'pulp celerybeat': {},
                            'pulp resource manager': {},
                            'pulp workers': {},
                            'shell': {'transport': 'local'},
                            'squid': {},
                        }
                    ),
                    config.PulpSystem(
                        hostname='second.example.com',
                        roles={
                            'api': {
                                'port': 2345,
                                'scheme': 'https',
                                'verify': False,
                            },
                            'pulp celerybeat': {},
                            'pulp resource manager': {},
                            'pulp workers': {},
                            'shell': {'transport': 'ssh'},
                            'squid': {}
                        }
                    ),
                ])
            )

    def test_read_old_config_file(self):
        """Ensure Pulp Smash can read old config file format."""
        open_ = mock.mock_open(read_data=OLD_CONFIG)
        with mock.patch.object(builtins, 'open', open_):
            cfg = config.PulpSmashConfig()
            with mock.patch.object(cfg, 'get_config_file_path'):
                with self.assertWarns(DeprecationWarning):
                    cfg = cfg.read()
        with self.subTest('check pulp_auth'):
            self.assertEqual(cfg.pulp_auth, ['username', 'password'])
        with self.subTest('check pulp_version'):
            self.assertEqual(cfg.pulp_version, config.Version('2.12'))
        with self.subTest('check systems'):
            self.assertEqual(
                cfg.systems,
                [
                    config.PulpSystem(
                        hostname='pulp.example.com',
                        roles={
                            'amqp broker': {'service': 'qpidd'},
                            'api': {
                                'scheme': 'https',
                                'verify': False,
                            },
                            'mongod': {},
                            'pulp cli': {},
                            'pulp celerybeat': {},
                            'pulp resource manager': {},
                            'pulp workers': {},
                            'shell': {'transport': 'ssh'},
                            'squid': {},
                        }
                    )
                ])


class HelperMethodsTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.config.PulpSmashConfig` helper methods."""

    def setUp(self):
        """Generate contents for a configuration file."""
        open_ = mock.mock_open(read_data=PULP_SMASH_CONFIG)
        with mock.patch.object(builtins, 'open', open_):
            cfg = config.PulpSmashConfig()
            with mock.patch.object(cfg, 'get_config_file_path'):
                self.cfg = cfg.read()

    def test_get_systems(self):
        """``get_systems`` returns proper result."""
        with self.subTest('role with multiplie matching systems'):
            result = [
                system.hostname for system in self.cfg.get_systems('api')]
            self.assertEqual(len(result), 2)
            self.assertEqual(
                sorted(result),
                sorted(['first.example.com', 'second.example.com'])
            )
        with self.subTest('role with single match system'):
            result = [
                system.hostname for system in self.cfg.get_systems('mongod')]
            self.assertEqual(len(result), 1)
            self.assertEqual(
                sorted(result),
                sorted(['first.example.com'])
            )

    def test_services_for_roles(self):
        """``services_for_roles`` returns proper result."""
        roles = {role: {} for role in config.ROLES}
        expected_roles = {
            'httpd',
            'mongod',
            'pulp_celerybeat',
            'pulp_resource_manager',
            'pulp_workers',
            'squid',
        }
        with self.subTest('no amqp broker service'):
            self.assertEqual(
                self.cfg.services_for_roles(roles),
                expected_roles
            )
        with self.subTest('qpidd amqp broker service'):
            roles['amqp broker']['service'] = 'qpidd'
            self.assertEqual(
                self.cfg.services_for_roles(roles),
                expected_roles.union({'qpidd'})
            )
        with self.subTest('rabbitmq amqp broker service'):
            roles['amqp broker']['service'] = 'rabbitmq'
            self.assertEqual(
                self.cfg.services_for_roles(roles),
                expected_roles.union({'rabbitmq'})
            )


class GetRequestsKwargsTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.config.PulpSmashConfig.get_requests_kwargs`."""

    @classmethod
    def setUpClass(cls):
        """Create a mock server config and call the method under test."""
        cls.attrs = _gen_attrs()
        cls.cfg = config.PulpSmashConfig(**cls.attrs)
        cls.kwargs = cls.cfg.get_requests_kwargs()

    def test_kwargs(self):
        """Assert that the method returns correct values."""
        self.assertEqual(
            self.kwargs,
            {
                'auth': tuple(self.attrs['pulp_auth']),
                'verify': True,
            }
        )

    def test_cfg_auth(self):
        """Assert that the method does not alter the config's ``auth``."""
        # _gen_attrs() returns ``auth`` as a list.
        self.assertIsInstance(self.cfg.pulp_auth, list)

    def test_kwargs_auth(self):
        """Assert that the method converts ``auth`` to a tuple."""
        self.assertIsInstance(self.kwargs['auth'], tuple)


class ReprTestCase(unittest.TestCase):
    """Test calling ``repr`` on a `pulp_smash.config.PulpSmashConfig`."""

    @classmethod
    def setUpClass(cls):
        """Generate attributes and call the method under test."""
        cls.attrs = _gen_attrs()
        cls.cfg = config.PulpSmashConfig(**cls.attrs)
        cls.result = repr(cls.cfg)

    def test_is_sane(self):
        """Assert that the result is in an expected set of results."""
        # permutations() → (((k1, v1), (k2, v2)), ((k2, v2), (k1, v1)))
        # kwargs_iter = ('k1=v1, k2=v2', 'k2=v2, k1=v1)
        kwargs_iter = (
            ', '.join(key + '=' + repr(val) for key, val in two_tuples)
            for two_tuples in itertools.permutations(self.attrs.items())
        )
        targets = tuple(
            'PulpSmashConfig({})'.format(arglist) for arglist in kwargs_iter
        )
        self.assertIn(self.result, targets)

    def test_can_eval(self):
        """Assert that the result can be parsed by ``eval``."""
        from pulp_smash.config import PulpSmashConfig, PulpSystem  # pylint:disable=unused-variable
        # pylint:disable=eval-used
        cfg = eval(self.result)
        with self.subTest('check pulp_version'):
            self.assertEqual(cfg.pulp_version, self.cfg.pulp_version)
        with self.subTest('check pulp_version'):
            self.assertEqual(cfg.pulp_version, self.cfg.pulp_version)
        with self.subTest('check systems'):
            self.assertEqual(cfg.systems, self.cfg.systems)


class GetConfigFilePathTestCase(unittest.TestCase):
    """Test ``pulp_smash.PulpSmashConfig.get_config_file_path``."""

    def test_success(self):
        """Assert the method returns a path when a config file is found."""
        with mock.patch.object(xdg.BaseDirectory, 'load_config_paths') as lcp:
            lcp.return_value = ('an_iterable', 'of_xdg', 'config_paths')
            with mock.patch.object(os.path, 'isfile') as isfile:
                isfile.return_value = True
                # pylint:disable=protected-access
                config.PulpSmashConfig().get_config_file_path()
        self.assertGreater(isfile.call_count, 0)

    def test_failures(self):
        """Assert the  method raises an exception when no config is found."""
        with mock.patch.object(xdg.BaseDirectory, 'load_config_paths') as lcp:
            lcp.return_value = ('an_iterable', 'of_xdg', 'config_paths')
            with mock.patch.object(os.path, 'isfile') as isfile:
                isfile.return_value = False
                with self.assertRaises(exceptions.ConfigFileNotFoundError):
                    # pylint:disable=protected-access
                    config.PulpSmashConfig().get_config_file_path()
        self.assertGreater(isfile.call_count, 0)


def _get_written_json(mock_obj):
    """Return the JSON that has been written to a mock `open` object."""
    # json.dump() calls write() for each individual JSON token.
    return json.loads(''.join(
        tuple(call_obj)[1][0]
        for call_obj
        in mock_obj().write.mock_calls
    ))
