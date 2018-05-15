# coding=utf-8
"""The entry point for Pulp Smash's command line interface."""
import json
import unittest

import click

from pulp_smash import config, exceptions, utils
from pulp_smash.config import PulpSmashConfig


def _raise_settings_not_found():
    """Raise `click.ClickException` for settings file not found."""
    result = click.ClickException(
        'there is no settings file. Use `pulp-smash settings create` to '
        'create one.'
    )
    result.exit_code = -1
    raise result


@click.group()
def pulp_smash():
    """Pulp Smash facilitates functional testing of Pulp."""


@pulp_smash.group()
@click.pass_context
def settings(ctx):
    """Manage settings file."""
    try:
        load_path = PulpSmashConfig.get_load_path()
    except exceptions.ConfigFileNotFoundError:
        load_path = None
    ctx.obj = {
        'load_path': load_path,
        'save_path': PulpSmashConfig.get_save_path()
    }


@settings.command('create')
@click.pass_context
def settings_create(ctx):  # pylint:disable=too-many-locals
    """Create a settings file."""
    path = ctx.obj['load_path']
    if path:
        click.echo(
            'A settings file already exists. Continuing will override it.'
        )
        click.confirm('Do you want to continue?', abort=True)
    else:
        path = ctx.obj['save_path']
    pulp_username = click.prompt('Pulp admin username', default='admin')
    pulp_password = click.prompt('Pulp admin password', default='admin')
    pulp_version = click.prompt('Pulp version')
    pulp_selinux_enabled = click.confirm(
        'Is SELinux supported in the test environment?',
        default=True
    )
    host_hostname = click.prompt('Host hostname')
    if click.confirm(
            "Is Pulp's API available over HTTPS (no for HTTP)?", default=True):
        host_api_scheme = 'https'
    else:
        host_api_scheme = 'http'

    if (host_api_scheme == 'https' and
            click.confirm('Verify HTTPS?', default=True)):
        certificate_path = click.prompt('SSL certificate path', default='')
        if not certificate_path:
            host_api_verify = True  # pragma: no cover
        else:
            host_api_verify = certificate_path
    else:
        host_api_verify = False

    click.echo(
        "By default, Pulp Smash will communicate with Pulp's API on the port "
        "number implied by the scheme. For example, if Pulp's API is "
        'available over HTTPS, then Pulp Smash will communicate on port 443.'
        "If Pulp's API is avaialable on a non-standard port, like 8000, then "
        'Pulp Smash needs to know about that.'
    )
    host_api_port = click.prompt('Pulp API port number', type=int, default=0)

    if click.confirm(
            'Is Pulp\'s message broker Qpid (no for RabbitMQ)?', default=True):
        amqp_broker = 'qpidd'
    else:
        amqp_broker = 'rabbitmq'
    using_ssh = not click.confirm(
        'Are you running Pulp Smash on the Pulp host?')
    if using_ssh:
        click.echo(
            'Pulp Smash will be configured to access the Pulp host using '
            'SSH. Because of that, some additional information is required.'
        )
        ssh_user = click.prompt('SSH username to use', default='root')
        click.echo(
            'Ensure ~/.ssh/controlmasters/ exists, and ensure the following '
            'is present in your ~/.ssh/config file:'
            '\n\n'
            '  Host {host_hostname}\n'
            '      StrictHostKeyChecking no\n'
            '      User {ssh_user}\n'
            '      UserKnownHostsFile /dev/null\n'
            '      ControlMaster auto\n'
            '      ControlPersist 10m\n'
            '      ControlPath ~/.ssh/controlmasters/%C\n'
            .format(host_hostname=host_hostname, ssh_user=ssh_user)
        )

    click.echo('Creating the settings file at {}...'.format(path))
    config_dict = {
        'pulp': {
            'auth': [pulp_username, pulp_password],
            'version': pulp_version,
            'selinux enabled': pulp_selinux_enabled,
        },
        'hosts': [{
            'hostname': host_hostname,
            'roles': {
                'amqp broker': {'service': amqp_broker},
                'api': {
                    'scheme': host_api_scheme,
                    'verify': host_api_verify,
                },
                'mongod': {},
                'pulp celerybeat': {},
                'pulp cli': {},
                'pulp resource manager': {},
                'pulp workers': {},
                'shell': {'transport': 'ssh' if using_ssh else 'local'},
                'squid': {},
            }
        }]
    }
    if host_api_port:
        config_dict['hosts'][0]['roles']['api']['port'] = host_api_port
    with open(path, 'w') as handler:
        handler.write(json.dumps(config_dict, indent=2, sort_keys=True))
    click.echo(
        'Settings file created, run `pulp-smash settings show` to show its '
        'contents.'
    )


@settings.command('path')
@click.pass_context
def settings_path(ctx):
    """Show the path to the settings file."""
    path = ctx.obj['load_path']
    if not path:
        _raise_settings_not_found()
    click.echo(path)


@settings.command('show')
@click.pass_context
def settings_show(ctx):
    """Show the settings file."""
    path = ctx.obj['load_path']
    if not path:
        _raise_settings_not_found()

    with open(path) as handle:
        click.echo(json.dumps(json.load(handle), indent=2, sort_keys=True))


@settings.command('validate')
@click.pass_context
def settings_validate(ctx):
    """Validate the settings file."""
    path = ctx.obj['load_path']
    if not path:
        _raise_settings_not_found()
    with open(path) as handle:
        config_dict = json.load(handle)
    try:
        config.validate_config(config_dict)
    except exceptions.ConfigValidationError as err:
        message = ('Invalid settings file: {}\n' .format(path))
        for error_message in err.error_messages:
            message += error_message
        result = click.ClickException(message)
        result.exit_code = -1
        raise result


@pulp_smash.command('smoke-tests')
def smoke_tests():
    """Print smoke tests, one per line.

    Sample usage:

        python -m unittest $(pulp-smash smoke-tests)
    """
    test_suite = unittest.TestSuite()
    test_suite.addTests(unittest.TestLoader().discover('pulp_smash.tests'))
    for smoke_test_name in _get_unique_smoke_test_names(test_suite):
        print(smoke_test_name)


def _get_unique_smoke_test_names(test_suite):
    """Recursively search for smoke tests, and return their unique names.

    :param test_suite: A ``unittest.TestSuite`` to recursively search through.
    :returns: A set of strings, each identifying a
        :class:`pulp_smash.utils.SmokeTest` within the given test suite.
    """
    return {
        '.'.join((type(test_case).__module__, type(test_case).__qualname__))
        for test_case in _get_smoke_tests(test_suite)
    }


def _get_smoke_tests(test_suite):
    """Recursively search for smoke tests, and yield them.

    :param test_suite: A ``unittest.TestSuite`` to recursively search through.
    :returns: :class:`pulp_smash.utils.SmokeTest` objects within the given test
        suite.
    """
    for test_case in _get_test_cases(test_suite):
        if isinstance(test_case, utils.SmokeTest):
            yield test_case


def _get_test_cases(test_suite):
    """Recursively search for ``unittest.TestCase`` objects, and yield them.

    :param test_suite: A ``unittest.TestSuite`` to recursively search through.
    :returns: ``unittest.TestCase`` objects within the given test suite.
    """
    for test_case_or_suite in test_suite:
        if isinstance(test_case_or_suite, unittest.TestCase):
            yield test_case_or_suite
        else:
            yield from _get_test_cases(test_case_or_suite)


if __name__ == '__main__':
    pulp_smash()  # pragma: no cover
