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
        "auth": ["username", "password"]
    }}''',
    '''\
    Customize the "base_url" and "auth" keys as needed. You may also want to
    add `"verify": False`. Doing so makes Pulp Smash ignore SSL verification
    errors.
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
    The provided command will run all tests, but any subset of tests may also
    be selected. For example, you may also run `python -m unittest2
    pulp_smash.tests.test_login`. Consult the unittest2 documentation for test
    selection syntax, and consult the source code to see which test modules are
    available.
    ''',
))


def main():
    """Provide usage instructions to the user."""
    cfg_path = join(
        # pylint:disable=protected-access
        BaseDirectory.save_config_path(ServerConfig._xdg_config_dir),
        ServerConfig._xdg_config_file
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
    message += '\n\n' + wrapper.fill(textwrap.dedent(MESSAGE[5]))
    print(message)


if __name__ == '__main__':
    main()
