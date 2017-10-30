# coding=utf-8
"""Unit tests for :mod:`pulp_smash.pulp_smash_cli`."""
import json
import os
import unittest
from unittest import mock

from click.testing import CliRunner
from pulp_smash import config, exceptions, pulp_smash_cli

from .test_config import OLD_CONFIG, PULP_SMASH_CONFIG


class BasePulpSmashCliTestCase(unittest.TestCase):
    """Base class for all pulp_smash_cli tests."""

    def setUp(self):
        """Configure a CliRunner."""
        super().setUp()
        self.cli_runner = CliRunner()


class MissingSettingsFileMixin(object):
    # pylint:disable=too-few-public-methods
    """Test missing settings file.

    Classes that inherit from this mixin should provide the
    ``settings_subcommand`` attribute set to the settings subcommand to run.
    """

    def test_missing_settings_file(self):
        """Ensure show outputs proper settings file."""
        with self.cli_runner.isolated_filesystem():
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                cfg.get_config_file_path.side_effect = (
                    exceptions.ConfigFileNotFoundError('No config file found.')
                )
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    [self.settings_subcommand],
                )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn(
                'there is no settings file. Use `pulp-smash settings create` '
                'to create one.',
                result.output,
            )


class SettingsCreateTestCase(BasePulpSmashCliTestCase):
    """Test ``pulp_smash.pulp_smash_cli.settings_create`` command."""

    def setUp(self):
        """Generate a default expected config dict."""
        super().setUp()
        self.expected_config_dict = {
            'pulp': {
                'auth': ['admin', 'admin'],
                'version': '2.13',
            },
            'systems': [{
                'hostname': 'pulp.example.com',
                'roles': {
                    'amqp broker': {'service': 'qpidd'},
                    'api': {
                        'scheme': 'https',
                        'verify': True,
                    },
                    'mongod': {},
                    'pulp celerybeat': {},
                    'pulp cli': {},
                    'pulp resource manager': {},
                    'pulp workers': {},
                    'shell': {'transport': 'ssh'},
                    'squid': {},
                }
            }]
        }

    def _test_common_logic(self, create_input, cfp_return_value=None):
        """Test common settings create logic.

        :param create_input: the input stream for the prompts.
        :param cfp_return_value: the return_value of
            ``PulpSmashConfig.get_config_file_path`` or, if None, it will have
            the side_effect of raising a
            :obj:`pulp_smash.exceptions.ConfigFileNotFoundError`.
        :return: the generated settings.json as string
        """
        with self.cli_runner.isolated_filesystem():
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                if cfp_return_value is None:
                    cfg.get_config_file_path.side_effect = (
                        exceptions.ConfigFileNotFoundError('Config not found.')
                    )
                else:
                    cfg.get_config_file_path.return_value = cfp_return_value
                cfg.default_config_file_path = 'settings.json'
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    ['create'],
                    input=create_input
                )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(
                'Creating the settings file at settings.json...\nSettings '
                'file created, run `pulp-smash settings show` to show its '
                'contents.\n',
                result.output,
            )
            self.assertTrue(os.path.isfile('settings.json'))
            with open('settings.json') as handler:
                return handler.read()

    def test_create_with_defaults(self):
        """Create settings file with default values values."""
        create_input = (
            '\n'  # admin username
            '\n'  # admin password
            '2.13\n'  # pulp version
            'pulp.example.com\n'  # system hostname
            '\n'  # published via HTTPS
            '\n'  # verify HTTPS
            '\n'  # API port
            '\n'  # using qpidd
            '\n'  # running on Pulp system
        )
        generated_settings = self._test_common_logic(create_input)
        self.assertEqual(
            json.loads(generated_settings), self.expected_config_dict)

    def test_settings_already_exists(self):
        """Create settings file by overriding existing one."""
        create_input = (
            'y\n'  # settings exists, continue
            '\n'  # admin username
            '\n'  # admin password
            '2.13\n'  # pulp version
            'pulp.example.com\n'  # system hostname
            '\n'  # published via HTTPS
            '\n'  # verify HTTPS
            '\n'  # API port
            '\n'  # using qpidd
            '\n'  # running on Pulp system
        )
        generated_settings = self._test_common_logic(
            create_input, 'settings.json')
        self.assertEqual(
            json.loads(generated_settings), self.expected_config_dict)

    def test_create_defaults_and_verify(self):
        """Create settings file with defaults and custom SSL certificate."""
        create_input = (
            '\n'  # admin username
            '\n'  # admin password
            '2.13\n'  # pulp version
            'pulp.example.com\n'  # system hostname
            '\n'  # published via HTTPS
            'y\n'  # verify HTTPS
            '/path/to/ssl/certificate\n'  # SSL certificate path
            '\n'  # API port
            '\n'  # using qpidd
            '\n'  # running on Pulp system
        )
        generated_settings = self._test_common_logic(create_input)
        self.expected_config_dict['systems'][0]['roles']['api']['verify'] = (
            '/path/to/ssl/certificate'
        )
        self.assertEqual(
            json.loads(generated_settings), self.expected_config_dict)

    def test_create_other_values(self):
        """Create settings file with custom values."""
        create_input = (
            'username\n'  # admin username
            'password\n'  # admin password
            '2.13\n'  # pulp version
            'pulp.example.com\n'  # system hostname
            'n\n'  # published via HTTPS
            '\n'  # API port
            'n\n'  # using qpidd
            'y\n'  # running on Pulp system
        )
        generated_settings = self._test_common_logic(create_input)
        self.expected_config_dict['pulp']['auth'] = ['username', 'password']
        system_roles = self.expected_config_dict['systems'][0]['roles']
        system_roles['amqp broker']['service'] = 'rabbitmq'
        system_roles['api']['scheme'] = 'http'
        system_roles['api']['verify'] = False
        system_roles['shell']['transport'] = 'local'
        self.assertEqual(
            json.loads(generated_settings), self.expected_config_dict)


class SettingsPathTestCase(BasePulpSmashCliTestCase, MissingSettingsFileMixin):
    """Test ``pulp_smash.pulp_smash_cli.settings_path`` command."""

    settings_subcommand = 'path'

    def test_settings_path(self):
        """Ensure path outputs proper settings file path."""
        with self.cli_runner.isolated_filesystem():
            with open('settings.json', 'w') as handler:
                handler.write(PULP_SMASH_CONFIG)
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                cfg.get_config_file_path.return_value = 'settings.json'
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    ['path'],
                )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(
                'settings.json',
                result.output,
            )


class SettingsShowTestCase(BasePulpSmashCliTestCase, MissingSettingsFileMixin):
    """Test ``pulp_smash.pulp_smash_cli.settings_show`` command."""

    settings_subcommand = 'show'

    def test_settings_show(self):
        """Ensure show outputs proper settings file."""
        with self.cli_runner.isolated_filesystem():
            with open('settings.json', 'w') as handler:
                handler.write(PULP_SMASH_CONFIG)
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                cfg.get_config_file_path.return_value = 'settings.json'
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    ['show'],
                )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(
                json.dumps(
                    json.loads(PULP_SMASH_CONFIG), indent=2, sort_keys=True),
                result.output,
            )


class SettingsValidateTestCase(
        BasePulpSmashCliTestCase, MissingSettingsFileMixin):
    """Test ``pulp_smash.pulp_smash_cli.settings_validate`` command."""

    settings_subcommand = 'validate'

    def test_valid_config(self):
        """Ensure validate does not complain about valid settings."""
        with self.cli_runner.isolated_filesystem():
            with open('settings.json', 'w') as handler:
                handler.write(PULP_SMASH_CONFIG)
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                cfg.get_config_file_path.return_value = 'settings.json'
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    ['validate'],
                )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, '')

    def test_invalid_config(self):
        """Ensure validate fails on invalid config file schema."""
        cfg_file = ''.join([
            line for line in PULP_SMASH_CONFIG.splitlines()
            if 'auth' not in line
        ])
        with self.cli_runner.isolated_filesystem():
            with open('settings.json', 'w') as handler:
                handler.write(cfg_file)
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                cfg.get_config_file_path.return_value = 'settings.json'
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    ['validate'],
                )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn(
                'invalid settings file settings.json',
                result.output,
            )
            self.assertIn(
                "Failed to validate config['pulp'] because 'auth' is a "
                'required property.',
                result.output,
            )

    def test_old_config_alert(self):
        """Ensure validate notifies about the old config format."""
        with self.cli_runner.isolated_filesystem():
            with open('settings.json', 'w') as handler:
                handler.write(OLD_CONFIG)
            with mock.patch.object(pulp_smash_cli, 'PulpSmashConfig') as psc:
                cfg = mock.MagicMock()
                psc.return_value = cfg
                cfg.get_config_file_path.return_value = 'settings.json'
                result = self.cli_runner.invoke(
                    pulp_smash_cli.settings,
                    ['validate'],
                )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn(
                'the settings file at settings.json appears to be following '
                'the old configuration file format, please update it like '
                'below:',
                result.output
            )
            self.assertIn(
                json.dumps(
                    config.convert_old_config(json.loads(OLD_CONFIG)),
                    indent=2,
                ),
                result.output,
            )
