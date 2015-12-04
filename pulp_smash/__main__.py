# coding=utf-8
"""The entry point for Pulp Smash's user interface."""
from __future__ import print_function, unicode_literals

import textwrap
from os.path import join
from pulp_smash.config import ServerConfig
from xdg import BaseDirectory

MESSAGE = tuple((
    '''\
    Pulp Smash's command line interface has not yet been fleshed out. Please
    create a configuration file at {} and call `python -m unittest2 discover
    pulp_smash.tests`. The configuration file should have this structure:
    ''',
    '''\
    {"default": {
        "base_url": "https://pulp.example.com",
        "auth": ["username", "password"],
        "verify": true,
        "version": "2.7.5"
    }}''',
    '''\
    The `verify` and `version` keys are completely optional. By default, Pulp
    Smash respects SSL verification procedures, but the `verify` option can be
    used to explicitly enable or disable SSL verification. By default, Pulp
    Smash assumes that the Pulp server under test is the absolute latest
    development version, but the `version` option can be used to explicitly run
    tests suitable for an older version of Pulp.
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
    variable like so: `PULP_SMASH_CONFIG_FILE=alternate-{} python -m unittest2
    discover pulp_smash.tests`. This variable should be a file name, not a
    path.
    ''',
    '''\
    The provided command will run all tests, but any subset of tests may also
    be selected. For example, you may also run `python -m unittest2
    pulp_smash.tests.test_login`. Consult the unittest2 documentation for test
    selection syntax, and consult the source code to see which test modules are
    available.
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
    wrapper.initial_indent = '* '
    wrapper.subsequent_indent = '  '
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[4]))
    message += '\n\n' + wrapper.fill(
        # pylint:disable=protected-access
        textwrap.dedent(MESSAGE[5].format(cfg._xdg_config_file))
    )
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[6]))
    print(message)


if __name__ == '__main__':
    main()
