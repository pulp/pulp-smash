# coding=utf-8
"""The entry point for Pulp Smash's user interface."""
import textwrap
from os.path import join

from xdg import BaseDirectory

from pulp_smash.config import ServerConfig

MESSAGE = tuple((
    '''\
    Please create a configuration file at {} and call `python3 -m unittest
    discover pulp_smash.tests`. The configuration file should have this
    structure:
    ''',
    '''\
    {
        "pulp": {
            "base_url": "https://pulp.example.com",
            "auth": ["username", "password"],
            "verify": true,
            "version": "2.7.5",
            "cli_transport": "local"
        },
        "pulp agent": {
            "base_url": "https://pulp-agent.example.com"
        }
    }''',
    '''\
    Each section provides information about a single Pulp-related service and
    the host on which that service is installed. The "pulp" and "pulp agent"
    sections tell about the Pulp and Pulp Agent services, respectively. The
    former is required. The latter is optional, and if omitted, relevant tests
    are skipped.
    ''',
    '''\
    The `verify`, `version` and `cli_transport` keys are optional. The `verify`
    option can be used to explicitly enable or disable SSL verification. The
    `version` option can be used to explicitly run tests suitable for an older
    version of Pulp. By default, Pulp Smash assumes that the Pulp server under
    test is the latest development version. The `cli_transport` key can be used
    to explicitly choose how to contact the Pulp server when executing shell
    commands. This can be set to "local" or "ssh". If omitted, Pulp Smash
    guesses which transport to use by comparing the hostname in the `base_url`
    against the current system's hostname.
    ''',
    '''\
    Notes:
    ''',
    '''\
    Pulp Smash abides by the XDG Base Directory Specification. The
    configuration file may be placed in any XDG-compliant location. The first
    configuration file found is used. Settings are not cascaded.
    ''',
    '''\
    A non-default configuration file can be selected with an environment
    variable like so: `PULP_SMASH_CONFIG_FILE=alternate-{} python3 -m unittest
    discover pulp_smash.tests`. This variable should be a file name, not a
    path.
    ''',
    '''\
    The provided command will run all tests, but any subset of tests may also
    be selected. For example, you may also run `python3 -m unittest
    pulp_smash.tests.platform.api_v2.test_login`. Consult the unittest
    documentation for test selection syntax, and consult the source code to see
    which test modules are available.
    ''',
))


def main():
    """Provide usage instructions to the user."""
    cfg = ServerConfig()
    cfg_path = join(
        # pylint:disable=protected-access
        BaseDirectory.save_config_path(cfg._xdg_config_dir),
        cfg._xdg_config_file
    )
    wrapper = textwrap.TextWrapper()
    message = ''
    message += wrapper.fill(textwrap.dedent(MESSAGE[0].format(cfg_path)))
    message += '\n\n' + MESSAGE[1]
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[2]))
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[3]))
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[4]))
    wrapper.initial_indent = '* '
    wrapper.subsequent_indent = '  '
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[5]))
    message += '\n\n' + wrapper.fill(
        # pylint:disable=protected-access
        textwrap.dedent(MESSAGE[6].format(cfg._xdg_config_file))
    )
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[7]))
    print(message)


if __name__ == '__main__':
    main()
