# coding=utf-8
"""The entry point for Pulp Smash's user interface."""
import textwrap
from os.path import join

from xdg import BaseDirectory

from pulp_smash.config import PulpSmashConfig

MESSAGE = tuple((
    """\
    Please create a configuration file at {} and call `python3 -m unittest
    discover pulp_smash.tests`. The configuration file should have this
    structure:
    """,
    """\
    {
        "pulp": {
            "auth": ["username", "password"],
            "version": "2.12.2"
        },
        "systems": [
            {
                "hostname": "pulp.example.com",
                "roles": {
                    "amqp broker": {"service": "qpidd"},
                    "api": {
                        "scheme": "https",
                        "verify": true
                    },
                    "mongod": {},
                    "pulp cli": {},
                    "pulp celerybeat": {},
                    "pulp resource manager": {},
                    "pulp workers": {},
                    "shell": {"transport": "local"},
                    "squid": {}
                }
            }
        ]
    }""",
    """\
    This configuration file format allows configuring either single machine
    Pulp deployment (as seen in the example above) or clustered Pulp deployment
    where each service can be installed on its own machine. The "pulp" section
    lets you declare the version of and authentication credentials for the Pulp
    deployment under test. The "systems" section provides information about
    each system that composes the deployment. A system must have its hostname
    and the roles that system has.
    """,
    """\
    Not all roles requires additional information. Currently, only the amqp
    broker, api and shell roles do. The amqp broker expects the service to be
    defined and it can be qpidd or rabbitmq. The api role means that httpd will
    be running on the system. The api's scheme allows specifying if the API
    should be accessed using http or https, verify allows specifying if the
    request SSL should be verified (true or false or a path to a certificate
    file). The shell role configures how the system will be accessed by using a
    local or ssh transport, only set local if Pulp Smash is running on that
    same system.
    """,
    """\
    Notes:
    """,
    """\
    Pulp Smash abides by the XDG Base Directory Specification. The
    configuration file may be placed in any XDG-compliant location. The first
    configuration file found is used. Settings are not cascaded.
    """,
    """\
    A non-default configuration file can be selected with an environment
    variable like so: `PULP_SMASH_CONFIG_FILE=alternate-{} python3 -m unittest
    discover pulp_smash.tests`. This variable should be a file name, not a
    path.
    """,
    """\
    The provided command will run all tests, but any subset of tests may also
    be selected. For example, you may also run `python3 -m unittest
    pulp_smash.tests.platform.api_v2.test_login`. Consult the unittest
    documentation for test selection syntax, and consult the source code to see
    which test modules are available.
    """,
))


def main():
    """Provide usage instructions to the user."""
    cfg = PulpSmashConfig()
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
