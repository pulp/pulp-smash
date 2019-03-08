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
    "hosts": [
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

# Identical to above, but s/hosts/systems/.
OLD_PULP_SMASH_CONFIG = """
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


def _gen_attrs():
    """Generate attributes for populating a ``PulpSmashConfig``.

    Example usage: ``PulpSmashConfig(**_gen_attrs())``.

    :returns: A dict. It populates all attributes in a ``PulpSmashConfig``.
    """
    return {
        "pulp_auth": [utils.uuid4() for _ in range(2)],
        "pulp_version": ".".join(
            str(random.randint(1, 150)) for _ in range(4)
        ),
        "pulp_selinux_enabled": True,
        "hosts": [
            config.PulpHost(
                hostname="pulp.example.com",
                roles={
                    "amqp broker": {"service": "qpidd"},
                    "api": {
                        "port": random.randint(1, 65535),
                        "scheme": "https",
                        "verify": True,
                    },
                    "mongod": {},
                    "pulp cli": {},
                    "pulp celerybeat": {},
                    "pulp resource manager": {},
                    "pulp workers": {},
                    "shell": {"transport": "local"},
                    "squid": {},
                },
            )
        ],
    }


class GetConfigTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.config.get_config`."""

    def test_cache_full(self):
        """No config is loaded from disk if the cache is populated."""
        with mock.patch.object(config, "_CONFIG"):
            with mock.patch.object(config.PulpSmashConfig, "load") as load:
                config.get_config()
        self.assertEqual(load.call_count, 0)

    def test_cache_empty(self):
        """A config is loaded from disk if the cache is empty."""
        with mock.patch.object(config, "_CONFIG", None):
            with mock.patch.object(config.PulpSmashConfig, "load") as load:
                config.get_config()
        self.assertEqual(load.call_count, 1)


class ValidateConfigTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.config.validate_config`."""

    def test_valid_config(self):
        """A valid config does not raise an exception."""
        self.assertIsNone(
            config.validate_config(json.loads(PULP_SMASH_CONFIG))
        )

    def test_invalid_config(self):
        """An invalid config raises an exception."""
        config_dict = json.loads(PULP_SMASH_CONFIG)
        config_dict["pulp"]["auth"] = []
        config_dict["hosts"][0]["hostname"] = ""
        with self.assertRaises(exceptions.ConfigValidationError):
            config.validate_config(config_dict)

    def test_config_missing_roles(self):
        """Missing required roles in config raises an exception."""
        config_dict = json.loads(PULP_SMASH_CONFIG)
        for host in config_dict["hosts"]:
            host["roles"].pop("api", None)
            host["roles"].pop("pulp workers", None)
        with self.assertRaises(exceptions.ConfigValidationError) as err:
            config.validate_config(config_dict)
        self.assertEqual(
            err.exception.message,
            "The following roles are not fulfilled by any hosts: api, pulp "
            "workers",
        )


class PulpSmashConfigFileTestCase(unittest.TestCase):
    """Verify the ``PULP_SMASH_CONFIG_FILE`` environment var is respected."""

    def test_var_set(self):
        """Set the environment variable."""
        os_environ = {"PULP_SMASH_CONFIG_FILE": utils.uuid4()}
        with mock.patch.dict(os.environ, os_environ, clear=True):
            config_file = (
                config.PulpSmashConfig._get_config_file()
            )  # pylint:disable=protected-access
        self.assertEqual(config_file, os_environ["PULP_SMASH_CONFIG_FILE"])

    def test_var_unset(self):
        """Do not set the environment variable."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config_file = (
                config.PulpSmashConfig._get_config_file()
            )  # pylint:disable=protected-access
        self.assertEqual(config_file, "settings.json")


class LoadTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.config.PulpSmashConfig.load`."""

    def test_load_config_file(self):
        """Ensure Pulp Smash can load the config file."""
        cfg = pulp_smash_config_load(PULP_SMASH_CONFIG)
        self.do_validate(cfg)

    def test_load_old_config_file(self):
        """Ensure Pulp Smash can load the config file."""
        with self.assertWarns(DeprecationWarning):
            cfg = pulp_smash_config_load(OLD_PULP_SMASH_CONFIG)
        self.do_validate(cfg)

    def do_validate(self, cfg):
        """Validate the attributes of a configuration object."""
        with self.subTest("check pulp_auth"):
            self.assertEqual(cfg.pulp_auth, ["username", "password"])
        with self.subTest("check pulp_version"):
            self.assertEqual(cfg.pulp_version, config.Version("2.12.1"))
        with self.subTest("check pulp_selinux_enabled"):
            self.assertEqual(cfg.pulp_selinux_enabled, True)
        with self.subTest("check hosts"):
            self.assertEqual(
                sorted(cfg.hosts),
                sorted(
                    [
                        config.PulpHost(
                            hostname="first.example.com",
                            roles={
                                "amqp broker": {"service": "qpidd"},
                                "api": {
                                    "port": 1234,
                                    "scheme": "https",
                                    "verify": True,
                                },
                                "mongod": {},
                                "pulp cli": {},
                                "pulp celerybeat": {},
                                "pulp resource manager": {},
                                "pulp workers": {},
                                "shell": {"transport": "local"},
                                "squid": {},
                            },
                        ),
                        config.PulpHost(
                            hostname="second.example.com",
                            roles={
                                "api": {
                                    "port": 2345,
                                    "scheme": "https",
                                    "verify": False,
                                },
                                "pulp celerybeat": {},
                                "pulp resource manager": {},
                                "pulp workers": {},
                                "shell": {"transport": "ssh"},
                                "squid": {},
                            },
                        ),
                    ]
                ),
            )


class HelperMethodsTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.config.PulpSmashConfig` helper methods."""

    def setUp(self):
        """Generate contents for a configuration file."""
        self.cfg = pulp_smash_config_load(PULP_SMASH_CONFIG)

    def test_get_hosts(self):
        """``get_hosts`` returns proper result."""
        with self.subTest("role with multiple matching hosts"):
            result = [host.hostname for host in self.cfg.get_hosts("api")]
            self.assertEqual(len(result), 2)
            self.assertEqual(
                sorted(result),
                sorted(["first.example.com", "second.example.com"]),
            )
        with self.subTest("role with single match host"):
            result = [host.hostname for host in self.cfg.get_hosts("mongod")]
            self.assertEqual(len(result), 1)
            self.assertEqual(sorted(result), sorted(["first.example.com"]))

    def test_get_services(self):
        """``get_services`` returns proper result."""
        # If set, the "amqp broker" role must have a "service" attribute.
        roles = {role: {} for role in config.P2_ROLES}
        del roles["amqp broker"]

        expected_roles = {
            "httpd",
            "mongod",
            "pulp_celerybeat",
            "pulp_resource_manager",
            "pulp_workers",
            "squid",
        }
        with self.subTest("no amqp broker service"):
            self.assertEqual(self.cfg.get_services(roles), expected_roles)

        roles["amqp broker"] = {"service": "qpidd"}
        with self.subTest("qpidd amqp broker service"):
            self.assertEqual(
                self.cfg.get_services(roles), expected_roles.union({"qpidd"})
            )

        roles["amqp broker"] = {"service": "rabbitmq"}
        with self.subTest("rabbitmq amqp broker service"):
            self.assertEqual(
                self.cfg.get_services(roles),
                expected_roles.union({"rabbitmq"}),
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
            {"auth": tuple(self.attrs["pulp_auth"]), "verify": True},
        )

    def test_cfg_auth(self):
        """Assert that the method does not alter the config's ``auth``."""
        # _gen_attrs() returns ``auth`` as a list.
        self.assertIsInstance(self.cfg.pulp_auth, list)

    def test_kwargs_auth(self):
        """Assert that the method converts ``auth`` to a tuple."""
        self.assertIsInstance(self.kwargs["auth"], tuple)


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
            ", ".join(key + "=" + repr(val) for key, val in two_tuples)
            for two_tuples in itertools.permutations(self.attrs.items())
        )
        targets = tuple(
            "PulpSmashConfig({})".format(arglist) for arglist in kwargs_iter
        )
        self.assertIn(self.result, targets)

    def test_can_eval(self):
        """Assert that the result can be parsed by ``eval``."""
        from pulp_smash.config import (
            PulpSmashConfig,
            PulpHost,
        )  # pylint:disable=unused-import,unused-variable

        # pylint:disable=eval-used
        cfg = eval(self.result)
        with self.subTest("check pulp_version"):
            self.assertEqual(cfg.pulp_version, self.cfg.pulp_version)
        with self.subTest("check pulp_version"):
            self.assertEqual(cfg.pulp_version, self.cfg.pulp_version)
        with self.subTest("check hosts"):
            self.assertEqual(cfg.hosts, self.cfg.hosts)


class GetConfigFileLoadPathTestCase(unittest.TestCase):
    """Test :meth:`pulp_smash.config.PulpSmashConfig.get_load_path`."""

    def test_success(self):
        """Assert the method returns a path when a config file is found."""
        with mock.patch.object(xdg.BaseDirectory, "load_config_paths") as lcp:
            lcp.return_value = ("/an/iterable", "/of/xdg", "/config/paths")
            with mock.patch.object(os.path, "exists") as exists:
                exists.return_value = True
                config.PulpSmashConfig.get_load_path()
        self.assertGreater(exists.call_count, 0)

    def test_failures(self):
        """Assert the  method raises an exception when no config is found."""
        with mock.patch.object(xdg.BaseDirectory, "load_config_paths") as lcp:
            lcp.return_value = ("/an/iterable", "/of/xdg", "/config/paths")
            with mock.patch.object(os.path, "exists") as exists:
                exists.return_value = False
                with self.assertRaises(exceptions.ConfigFileNotFoundError):
                    config.PulpSmashConfig.get_load_path()
        self.assertGreater(exists.call_count, 0)


def _get_written_json(mock_obj):
    """Return the JSON that has been written to a mock `open` object."""
    # json.dump() calls write() for each individual JSON token.
    return json.loads(
        "".join(
            tuple(call_obj)[1][0] for call_obj in mock_obj().write.mock_calls
        )
    )


def pulp_smash_config_load(config_str):
    """Load an in-memory configuration file.

    :param config_str: A string. An in-memory configuration file.
    :return: A :class:`pulp_smash.config.PulpSmashConfig` object, populated
        from the configuration file.
    """
    with mock.patch.object(
        builtins, "open", mock.mock_open(read_data=config_str)
    ):
        with mock.patch.object(config.PulpSmashConfig, "get_load_path"):
            return config.PulpSmashConfig.load()
