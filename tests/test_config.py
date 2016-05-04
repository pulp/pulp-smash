# coding=utf-8
"""Unit tests for :mod:`pulp_smash.config`."""
from __future__ import unicode_literals

import itertools
import json
import os
import random
try:  # try Python 3 import first
    import builtins
except ImportError:
    import __builtin__ as builtins  # pylint:disable=C0411,E0401

import mock
import unittest2
import xdg

from pulp_smash import config, exceptions, utils


def _gen_attrs():
    """Generate attributes for populating a ``ServerConfig``.

    Example usage: ``ServerConfig(**_gen_attrs())``.

    :returns: A dict. It populates all attributes in a ``ServerConfig``.
    """
    attrs = {
        key: utils.uuid4() for key in ('base_url', 'cli_transport', 'verify')
    }
    attrs['auth'] = [utils.uuid4() for _ in range(2)]
    attrs['version'] = '.'.join(
        type('')(random.randint(1, 150)) for _ in range(4)
    )
    return attrs


class GetConfigTestCase(unittest2.TestCase):
    """Test :func:`pulp_smash.config.get_config`."""

    def test_cache_full(self):
        """No config is read from disk if the cache is populated."""
        with mock.patch.object(config, '_CONFIG'):
            with mock.patch.object(config.ServerConfig, 'read') as read:
                config.get_config()
        self.assertEqual(read.call_count, 0)

    def test_cache_empty(self):
        """A config is read from disk if the cache is empty."""
        with mock.patch.object(config, '_CONFIG', None):
            with mock.patch.object(config.ServerConfig, 'read') as read:
                config.get_config()
        self.assertEqual(read.call_count, 1)


class InitTestCase(unittest2.TestCase):
    """Test :class:`pulp_smash.config.ServerConfig` instantiation."""

    @classmethod
    def setUpClass(cls):
        """Generate some attributes and use them to instantiate a config."""
        cls.kwargs = _gen_attrs()
        cls.cfg = config.ServerConfig(**cls.kwargs)

    def test_public_attrs(self):
        """Assert that public attributes have correct values."""
        attrs = config._public_attrs(self.cfg)  # pylint:disable=W0212
        attrs['version'] = type('')(attrs['version'])
        self.assertEqual(self.kwargs, attrs)

    def test_private_attrs(self):
        """Assert that private attributes have been set."""
        for attr in ('_section', '_xdg_config_file', '_xdg_config_dir'):
            with self.subTest(attr):
                self.assertIsNotNone(getattr(self.cfg, attr))


class PulpSmashConfigFileTestCase(unittest2.TestCase):
    """Verify the ``PULP_SMASH_CONFIG_FILE`` environment var is respected."""

    def test_var_set(self):
        """Set the environment variable."""
        os_environ = {'PULP_SMASH_CONFIG_FILE': utils.uuid4()}
        with mock.patch.dict(os.environ, os_environ, clear=True):
            cfg = config.ServerConfig()
        self.assertEqual(
            cfg._xdg_config_file,  # pylint:disable=protected-access
            os_environ['PULP_SMASH_CONFIG_FILE']
        )

    def test_var_unset(self):
        """Do not set the environment variable."""
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = config.ServerConfig()
        # pylint:disable=protected-access
        self.assertEqual(cfg._xdg_config_file, 'settings.json')


class ReadTestCase(unittest2.TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.read`."""

    def setUp(self):
        """Generate contents for a configuration file."""
        self.config_file = {'pulp': _gen_attrs()}

    def test_read_section(self):
        """Read a section from the configuration file.

        Assert that values from the configuration file are present on the
        resultant :class:`pulp_smash.config.ServerConfig` object.
        """
        open_ = mock.mock_open(read_data=json.dumps(self.config_file))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                cfg = config.ServerConfig().read()
        self.assertEqual(self.config_file['pulp']['base_url'], cfg.base_url)

    def test_read_nonexistent_section(self):
        """Read a non-existent section from the configuration file.

        Assert a :class:`pulp_smash.exceptions.ConfigFileSectionNotFoundError`
        is raised.
        """
        open_ = mock.mock_open(read_data=json.dumps(self.config_file))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                with self.assertRaises(
                    exceptions.ConfigFileSectionNotFoundError
                ):
                    config.ServerConfig().read('foo')

    def test_read_default_section(self):
        """Read from a configuration file with a section named 'default'."""
        self.config_file['default'] = self.config_file.pop('pulp')
        open_ = mock.mock_open(read_data=json.dumps(self.config_file))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                with self.assertWarns(DeprecationWarning):
                    cfg = config.ServerConfig().read()
        self.assertEqual(self.config_file['default']['base_url'], cfg.base_url)


class SectionsTestCase(unittest2.TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.sections`."""

    @classmethod
    def setUpClass(cls):
        """Read a mock configuration file's sections. Save relevant objects."""
        cls.config = random.choice((
            {},
            {'foo': None},
            {'foo': None, 'bar': None, 'biz': None},
        ))
        cls.open_ = mock.mock_open(read_data=json.dumps(cls.config))
        with mock.patch.object(builtins, 'open', cls.open_):
            with mock.patch.object(config, '_get_config_file_path'):
                cls.sections = config.ServerConfig().sections()

    def test_sections(self):
        """Assert that the correct section names are returned."""
        self.assertEqual(set(self.config.keys()), self.sections)

    def test_open(self):
        """Assert that ``open`` was called once."""
        self.assertEqual(self.open_.call_count, 1)


class GetRequestsKwargsTestCase(unittest2.TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.get_requests_kwargs`."""

    @classmethod
    def setUpClass(cls):
        """Create a mock server config and call the method under test."""
        cls.attrs = _gen_attrs()
        cls.cfg = config.ServerConfig(**cls.attrs)
        cls.kwargs = cls.cfg.get_requests_kwargs()

    def test_kwargs(self):
        """Assert that the method returns correct values."""
        attrs = self.attrs.copy()
        for key in ('base_url', 'cli_transport', 'version'):
            del attrs[key]
        attrs['auth'] = tuple(attrs['auth'])
        self.assertEqual(attrs, self.kwargs)

    def test_cfg_auth(self):
        """Assert that the method does not alter the config's ``auth``."""
        # _gen_attrs() returns ``auth`` as a list.
        self.assertIsInstance(self.cfg.auth, list)

    def test_kwargs_auth(self):
        """Assert that the method converts ``auth`` to a tuple."""
        self.assertIsInstance(self.kwargs['auth'], tuple)


class ReprTestCase(unittest2.TestCase):
    """Test calling ``repr`` on a :class:`pulp_smash.config.ServerConfig`."""

    @classmethod
    def setUpClass(cls):
        """Generate attributes and call the method under test."""
        cls.attrs = _gen_attrs()
        cls.result = repr(config.ServerConfig(**cls.attrs))

    def test_is_sane(self):
        """Assert that the result is in an expected set of results."""
        # permutations() → (((k1, v1), (k2, v2)), ((k2, v2), (k1, v1)))
        # kwargs_iter = ('k1=v1, k2=v2', 'k2=v2, k1=v1)
        kwargs_iter = (
            ', '.join(key + '=' + repr(val) for key, val in two_tuples)
            for two_tuples in itertools.permutations(self.attrs.items())
        )
        targets = tuple(
            'ServerConfig({})'.format(arglist) for arglist in kwargs_iter
        )
        self.assertIn(self.result, targets)

    def test_can_eval(self):
        """Assert that the result can be parsed by ``eval``."""
        from pulp_smash.config import ServerConfig  # noqa
        # pylint:disable=eval-used
        self.assertEqual(self.result, repr(eval(self.result)))


class DeleteTestCase(unittest2.TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.delete`."""

    def test_delete_default(self):
        """Assert that the method can delete the default section."""
        open_ = mock.mock_open(read_data=json.dumps({'pulp': {}}))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                config.ServerConfig().delete()
        self.assertEqual(_get_written_json(open_), {})

    def test_delete_section(self):
        """Assert that the method can delete a specified section."""
        attrs = {'foo': {}, 'bar': {}}
        section = random.choice(tuple(attrs.keys()))
        open_ = mock.mock_open(read_data=json.dumps(attrs))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                config.ServerConfig().delete(section)
        del attrs[section]
        self.assertEqual(_get_written_json(open_), attrs)


class SaveTestCase(unittest2.TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.save`."""

    def test_save_default(self):
        """Assert that the method can save the default section."""
        attrs = _gen_attrs()
        open_ = mock.mock_open(read_data=json.dumps({}))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                config.ServerConfig(**attrs).save()
        self.assertEqual(_get_written_json(open_), {'pulp': attrs})

    def test_save_section(self):
        """Assert that the method can save a specified section."""
        # `cfg` is the existing config file. We generate a new config as
        # `attrs` and save it into section `section`.
        cfg = {'existing': {}}
        section = utils.uuid4()
        attrs = _gen_attrs()
        open_ = mock.mock_open(read_data=json.dumps(cfg))
        with mock.patch.object(builtins, 'open', open_):
            with mock.patch.object(config, '_get_config_file_path'):
                config.ServerConfig(**attrs).save(section)
        cfg[section] = attrs
        self.assertEqual(_get_written_json(open_), cfg)


class GetConfigFilePathTestCase(unittest2.TestCase):
    """Test ``pulp_smash.config._get_config_file_path``."""

    def test_success(self):
        """Assert the method returns a path when a config file is found."""
        with mock.patch.object(xdg.BaseDirectory, 'load_config_paths') as lcp:
            lcp.return_value = ('an_iterable', 'of_xdg', 'config_paths')
            with mock.patch.object(os.path, 'isfile') as isfile:
                isfile.return_value = True
                # pylint:disable=protected-access
                config._get_config_file_path(utils.uuid4(), utils.uuid4())
        self.assertGreater(isfile.call_count, 0)

    def test_failures(self):
        """Assert the  method raises an exception when no config is found."""
        with mock.patch.object(xdg.BaseDirectory, 'load_config_paths') as lcp:
            lcp.return_value = ('an_iterable', 'of_xdg', 'config_paths')
            with mock.patch.object(os.path, 'isfile') as isfile:
                isfile.return_value = False
                with self.assertRaises(exceptions.ConfigFileNotFoundError):
                    # pylint:disable=protected-access
                    config._get_config_file_path(utils.uuid4(), utils.uuid4())
        self.assertGreater(isfile.call_count, 0)


def _get_written_json(mock_obj):
    """Return the JSON that has been written to a mock `open` object."""
    # json.dump() calls write() for each individual JSON token.
    return json.loads(''.join(
        tuple(call_obj)[1][0]
        for call_obj
        in mock_obj().write.mock_calls
    ))
