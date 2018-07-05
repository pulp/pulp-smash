# coding=utf-8
"""The entry point for Pulp Smash's command line interface."""
import json
import sys

import click
from packaging.version import Version

from pulp_smash import config, exceptions
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
def settings_create(ctx):
    """Create a settings file."""
    # Choose where and whether to save the configuration file.
    path = ctx.obj['load_path']
    if path:
        click.confirm(
            'A settings file already exists. Continuing will override it. '
            'Do you want to continue?',
            abort=True,
        )
    else:
        path = ctx.obj['save_path']

    # Get information about Pulp.
    pulp_config = {'pulp': _get_pulp_properties()}
    pulp_config['hosts'] = [
        _get_host_properties(pulp_config['pulp']['version'])
    ]
    pulp_config['pulp']['version'] = str(pulp_config['pulp']['version'])
    try:
        config.validate_config(pulp_config)  # This should NEVER fail!
    except exceptions.ConfigValidationError:
        print(
            'An internal error has occurred. Please report this to the Pulp '
            'Smash developers at https://github.com/PulpQE/pulp-smash/issues',
            file=sys.stderr,
        )
        raise

    # Write the config to disk.
    with open(path, 'w') as handler:
        handler.write(json.dumps(pulp_config, indent=2, sort_keys=True))
    click.echo('Settings written to {}.'.format(path))


def _get_pulp_properties():
    """Get information about the Pulp application as a whole."""
    version = click.prompt(
        'Which version of Pulp is under test?',
        type=PulpVersionType()
    )
    username = click.prompt(
        "What is the Pulp administrative user's username?",
        default='admin',
        type=click.STRING,
    )
    password = click.prompt(
        "What is the Pulp administrative user's password?",
        default='admin',
        type=click.STRING,
    )
    # We could make this default to "false" if version >= 3, but it seems
    # better to assume that Pulp is secure by default, and to annoy everyone
    # about Pulp 3's lack of security.
    selinux_enabled = click.confirm(
        'Is SELinux supported on the Pulp hosts?',
        default=True,
    )
    return {
        'auth': [username, password],
        'selinux enabled': selinux_enabled,
        'version': version,
    }


def _get_host_properties(pulp_version):
    """Get information about a Pulp host."""
    if pulp_version < Version('3'):
        return _get_v2_host_properties(pulp_version)
    return _get_v3_host_properties(pulp_version)


def _get_v2_host_properties(pulp_version):
    """Get information about a Pulp 2 host."""
    hostname = _get_hostname()
    amqp_broker = _get_amqp_broker_role()
    api_role = _get_api_role(pulp_version)
    shell_role = _get_shell_role(hostname)
    return {
        'hostname': hostname,
        'roles': {
            'amqp broker': {'service': amqp_broker},
            'api': api_role,
            'mongod': {},
            'pulp celerybeat': {},
            'pulp cli': {},
            'pulp resource manager': {},
            'pulp workers': {},
            'shell': shell_role,
            'squid': {},
        }
    }


def _get_v3_host_properties(pulp_version):
    """Get information about a Pulp 3 host."""
    hostname = _get_hostname()
    api_role = _get_api_role(pulp_version)
    shell_role = _get_shell_role(hostname)
    return {
        'hostname': hostname,
        'roles': {
            'api': api_role,
            'pulp resource manager': {},
            'pulp workers': {},
            'redis': {},
            'shell': shell_role,
        }
    }


def _get_hostname():
    """Get the Pulp host's hostname."""
    return click.prompt("What is the Pulp host's hostname?", type=click.STRING)


def _get_amqp_broker_role():
    """Get information for the "amqp broker" role."""
    return click.prompt(
        "What service backs Pulp's AMQP broker?",
        default='qpidd',
        type=click.Choice(('qpidd', 'rabbitmq')),
    )


def _get_api_role(pulp_version):
    """Get information for the "api" role."""
    api_role = {}

    # Get "scheme"
    api_role['scheme'] = click.prompt(
        "What scheme should be used when communicating with Pulp's API?",
        default='https',
        type=click.Choice(('https', 'http')),
    )

    # Get "verify"
    if (api_role['scheme'] == 'https' and
            click.confirm('Verify HTTPS?', default=True)):
        certificate_path = click.prompt(
            'SSL certificate path',
            default='',
            type=click.Path(),
        )
        api_role['verify'] = certificate_path if certificate_path else True
    else:
        api_role['verify'] = False

    # Get "port"
    click.echo(
        "By default, Pulp Smash will communicate with Pulp's API on the port "
        "number implied by the scheme. For example, if Pulp's API is "
        'available over HTTPS, then Pulp Smash will communicate on port 443. '
        "If Pulp's API is available on a non-standard port, like 8000, then "
        'Pulp Smash needs to know about that.'
    )
    port = click.prompt('Pulp API port number', default=0, type=click.INT)
    if port:
        api_role['port'] = port

    # Get "service"
    api_role['service'] = click.prompt(
        "What web server service backs Pulp's API?",
        default='httpd' if pulp_version < Version('3') else 'nginx',
        type=click.Choice(('httpd', 'nginx'))
    )

    return api_role


def _get_shell_role(hostname):
    if click.confirm('Is Pulp Smash installed on the same host as Pulp?'):
        click.echo('Pulp Smash will access the Pulp host using a local shell.')
        return {'transport': 'local'}
    click.echo('Pulp Smash will access the Pulp host using SSH.')
    ssh_user = click.prompt('SSH username', default='root')
    click.echo(
        'Ensure the SSH user has passwordless sudo access, ensure '
        '~/.ssh/controlmasters/ exists, and ensure the following is '
        'present in your ~/.ssh/config file:'
        '\n\n'
        '  Host {}\n'
        '    StrictHostKeyChecking no\n'
        '    User {}\n'
        '    UserKnownHostsFile /dev/null\n'
        '    ControlMaster auto\n'
        '    ControlPersist 10m\n'
        '    ControlPath ~/.ssh/controlmasters/%C\n'
        .format(hostname, ssh_user)
    )
    return {'transport': 'ssh'}


class PulpVersionType(click.ParamType):
    """Define the possible values for a Pulp version string.

    A Pulp version string is valid if it can be cast to a
    ``packaging.version.Version`` object, if it is at least 2, and if it is
    less than 4.
    """

    name = 'Pulp version'

    def convert(self, value, param, ctx):
        """Convert a version string to a ``Version`` object."""
        converted_ver = Version(value)
        if converted_ver < Version('2') or converted_ver >= Version('4'):
            self.fail(
                "Pulp Smash can test Pulp version 2.y and 3.y. It can't test "
                'Pulp version {}.'.format(converted_ver),
                param,
                ctx
            )
        return converted_ver


@settings.command('path')
@click.pass_context
def settings_path(ctx):  # noqa:D401
    """Deprecated in favor of 'load-path'."""
    ctx.forward(settings_load_path)


@settings.command('load-path')
@click.pass_context
def settings_load_path(ctx):
    """Print the path from which settings are loaded.

    Search several paths for a settings file, in order of preference. If a file
    is found, print its path. Otherwise, return a non-zero exit code. This load
    path is used by sibling commands such as "show".
    """
    path = ctx.obj['load_path']
    if not path:
        _raise_settings_not_found()
    click.echo(path)


@settings.command('save-path')
@click.pass_context
def settings_save_path(ctx):
    """Print the path to which settings are saved.

    As a side-effect, create all directories in the path that don't yet exist.
    As a result, it's safe to execute a Bash expression such as:

        echo '{...}' > "$(pulp-smash settings save-path)"

    This save path is used by sibling commands such as "create".
    """
    click.echo(ctx.obj['save_path'])


@settings.command('show')
@click.pass_context
def settings_show(ctx):
    """Print the settings file."""
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
        raise click.ClickException(
            '{} is invalid: '.format(path) + err.message
        ) from err


if __name__ == '__main__':
    pulp_smash()  # pragma: no cover
