# coding=utf-8
"""Unit tests for :mod:`pulp_smash.config`."""
from __future__ import unicode_literals

import json
import os
from itertools import permutations
from mock import mock_open, patch
from pulp_smash import config
from pulp_smash.config import ServerConfig, _PUBLIC_ATTRS
from random import choice, randint
from unittest2 import TestCase

from sys import version_info
if version_info.major == 2:
    # The `__builtins__` module (note the "s") also provides the `open`
    # function. However, that module is an implementation detail for CPython 2,
    # so it should not be relied on.
    import __builtin__ as builtins  # pylint:disable=import-error
else:
    import builtins  # pylint:disable=import-error


def _gen_attrs():
    """Generate attributes for populating a ``ServerConfig``.

    Example usage: ``ServerConfig(**_gen_attrs())``.

    :returns: A dict. It populates all attributes in a ``ServerConfig``.

    """
    attrs = {key: randint(-1000, 1000) for key in ('base_url', 'verify')}
    attrs['auth'] = [randint(-1000, 1000), randint(-1000, 1000)]
    return attrs


class InitTestCase(TestCase):
    """Test :class:`pulp_smash.config.ServerConfig` instantiation."""

    @classmethod
    def setUpClass(cls):
        """Generate some attributes and use them to instantiate a config."""
        cls.kwargs = _gen_attrs()
        cls.cfg = ServerConfig(**cls.kwargs)

    def test_public_attrs(self):
        """Assert that public attributes have correct values."""
        attrs = {attr: getattr(self.cfg, attr) for attr in _PUBLIC_ATTRS}
        self.assertEqual(self.kwargs, attrs)

    def test_private_attrs(self):
        """Assert that private attributes have been set."""
        for attr in ('_section', '_xdg_config_file', '_xdg_config_dir'):
            with self.subTest(attr):
                self.assertIsNotNone(getattr(self.cfg, attr))


class PulpSmashConfigFileTestCase(TestCase):
    """Verify the ``PULP_SMASH_CONFIG_FILE`` environment var is respected."""

    def test_var_set(self):
        """Set the environment variable."""
        os_environ = {'PULP_SMASH_CONFIG_FILE': type('')(randint(1, 1000))}
        with patch.dict(os.environ, os_environ, clear=True):
            cfg = ServerConfig()
        self.assertEqual(
            cfg._xdg_config_file,  # pylint:disable=protected-access
            os_environ['PULP_SMASH_CONFIG_FILE']
        )

    def test_var_unset(self):
        """Do not set the environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            cfg = ServerConfig()
        # pylint:disable=protected-access
        self.assertEqual(cfg._xdg_config_file, 'settings.json')


class ReadTestCase(TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.read`."""

    @classmethod
    def setUpClass(cls):
        """Read a mock configuration file section. Save relevant objects."""
        cls.attrs = _gen_attrs()  # config section values
        cls.open_ = mock_open(read_data=json.dumps({'default': cls.attrs}))
        with patch.object(builtins, 'open', cls.open_):
            with patch.object(config, '_get_config_file_path'):
                cls.cfg = ServerConfig().read()

    def test_attrs(self):
        """Assert that config file values are assigned to a config obj."""
        attrs = {attr: getattr(self.cfg, attr) for attr in _PUBLIC_ATTRS}
        self.assertEqual(self.attrs, attrs)

    def test_open(self):
        """Assert that ``open`` was called once."""
        self.assertEqual(self.open_.call_count, 1)


class SectionsTestCase(TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.sections`."""

    @classmethod
    def setUpClass(cls):
        """Read a mock configuration file's sections. Save relevant objects."""
        cls.config = choice((
            {},
            {'foo': None},
            {'foo': None, 'bar': None, 'biz': None},
        ))
        cls.open_ = mock_open(read_data=json.dumps(cls.config))
        with patch.object(builtins, 'open', cls.open_):
            with patch.object(config, '_get_config_file_path'):
                cls.sections = ServerConfig().sections()

    def test_sections(self):
        """Assert that the correct section names are returned."""
        self.assertEqual(set(self.config.keys()), self.sections)

    def test_open(self):
        """Assert that ``open`` was called once."""
        self.assertEqual(self.open_.call_count, 1)


class GetRequestsKwargsTestCase(TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.get_requests_kwargs`."""

    @classmethod
    def setUpClass(cls):
        """Create a mock server config and call the method under test."""
        cls.attrs = _gen_attrs()
        cls.cfg = ServerConfig(**cls.attrs)
        cls.kwargs = cls.cfg.get_requests_kwargs()

    def test_kwargs(self):
        """Assert that the method returns correct values."""
        attrs = self.attrs.copy()
        del attrs['base_url']
        attrs['auth'] = tuple(attrs['auth'])
        self.assertEqual(attrs, self.kwargs)

    def test_cfg_auth(self):
        """Assert that the method does not alter the config's ``auth``."""
        # _gen_attrs() returns ``auth`` as a list.
        self.assertIsInstance(self.cfg.auth, list)

    def test_kwargs_auth(self):
        """Assert that the method converts ``auth`` to a tuple."""
        self.assertIsInstance(self.kwargs['auth'], tuple)


class ReprTestCase(TestCase):
    """Test calling ``repr`` on a :class:`pulp_smash.config.ServerConfig`."""

    @classmethod
    def setUpClass(cls):
        """Generate attributes and call the method under test."""
        cls.attrs = _gen_attrs()
        cls.result = repr(ServerConfig(**cls.attrs))

    def test_is_sane(self):
        """Assert that the result is in an expected set of results."""
        # arglists = (
        #     'key3=val3, key2=val2, key1=val1',
        #     'key3=val3, key1=val1, key2=val2',
        #     …
        # )
        arglists = (
            ', '.join('{}={}'.format(key, val) for key, val in arglist)
            for arglist in permutations(self.attrs.items())
        )
        targets = (
            'ServerConfig({})'.format(arglist) for arglist in arglists
        )
        self.assertIn(self.result, targets)

    def test_can_eval(self):
        """Assert that the result can be parsed by ``eval``."""
        # pylint:disable=eval-used
        self.assertEqual(self.result, repr(eval(self.result)))


class DeleteTestCase(TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.delete`."""

    def test_delete_default(self):
        """Assert that the method can delete the default section."""
        open_ = mock_open(read_data=json.dumps({'default': {}}))
        with patch.object(builtins, 'open', open_):
            with patch.object(config, '_get_config_file_path'):
                ServerConfig().delete()
        self.assertEqual(_get_written_json(open_), {})

    def test_delete_section(self):
        """Assert that the method can delete a specified section."""
        attrs = {'foo': {}, 'bar': {}}
        section = choice(tuple(attrs.keys()))
        open_ = mock_open(read_data=json.dumps(attrs))
        with patch.object(builtins, 'open', open_):
            with patch.object(config, '_get_config_file_path'):
                ServerConfig().delete(section)
        del attrs[section]
        self.assertEqual(_get_written_json(open_), attrs)


class SaveTestCase(TestCase):
    """Test :meth:`pulp_smash.config.ServerConfig.save`."""

    def test_save_default(self):
        """Assert that the method can save the default section."""
        attrs = _gen_attrs()
        open_ = mock_open(read_data=json.dumps({}))
        with patch.object(builtins, 'open', open_):
            with patch.object(config, '_get_config_file_path'):
                ServerConfig(**attrs).save()
        self.assertEqual(_get_written_json(open_), {'default': attrs})

    def test_save_section(self):
        """Assert that the method can save a specified section."""
        # `cfg` is the existing config file. We generate a new config as
        # `attrs` and save it into section `section`.
        cfg = {'existing': {}}
        section = type('')(randint(1, 1000))
        attrs = _gen_attrs()
        open_ = mock_open(read_data=json.dumps(cfg))
        with patch.object(builtins, 'open', open_):
            with patch.object(config, '_get_config_file_path'):
                ServerConfig(**attrs).save(section)
        cfg[section] = attrs
        self.assertEqual(_get_written_json(open_), cfg)


def _get_written_json(mock_obj):
    """Return the JSON that has been written to a mock `open` object."""
    # json.dump() calls write() for each individual JSON token.
    return json.loads(''.join(
        tuple(call_obj)[1][0]
        for call_obj
        in mock_obj().write.mock_calls
    ))
