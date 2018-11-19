Usage
=====

Location: :doc:`/index` → :doc:`/usage`

Utilities
---------

Pulp-Smash provides utilities to help writing tests for Pulp2 and Pulp3.
The most important utilities are:

- API  :doc:`/api/pulp_smash.api`
- CLI  :doc:`/api/pulp_smash.cli`
- Utils  
    - General :doc:`/api/pulp_smash.utils`
    - Pulp2 :doc:`/api/pulp_smash.pulp2.utils`
    - Pulp3 :doc:`/api/pulp_smash.pulp3.utils`

The `pulp-smash` CLI 
--------------------

The command `pulp-smash` is provided to help with `settings` management and test style `lint`::

    $ pulp-smash --help         
    Usage: pulp-smash [OPTIONS] COMMAND [ARGS]...

    Pulp Smash facilitates functional testing of Pulp.

    Options:
    --help  Show this message and exit.

    Commands:
    lint      Lint input files.
    settings  Manage settings file.


Settings
~~~~~~~~

The command `pulp-smash settings` can be used to manage the configuration of your `pulp-smash` test runner.
 
See more info in :doc:`/configuration`

Available subcommands::

    $ pulp-smash settings --help
    Usage: pulp-smash settings [OPTIONS] COMMAND [ARGS]...

    Manage settings file.

    Options:
    --help  Show this message and exit.

    Commands:
    create     Create a settings file.
    load-path  Print the path from which settings are...
    path       Deprecated in favor of 'load-path'.
    save-path  Print the path to which settings are saved.
    show       Print the settings file.
    validate   Validate the settings file.


Lint
~~~~

This command can be used to check for code style errors in Pulp functional tests 
in any repository the tests are located.

For example, to check coding style for only the files that were changed in git::

    $ pulp-smash lint --picked

To check style for all files under a certain path::

    $ pulp-smash lint pulpcore/tests/funtional

The lint command uses only `flake8` but it is also possible to check using `pylint`::

    $ pulp-smash lint path/to/tests/ --pylint 

Complete subcommand help::

    $ pulp-smash lint --help
    Usage: pulp-smash lint [OPTIONS] [FILEPATH]

    Lint input files.

    Usage: `pulp-smash lint /path/to/files/`

    Options:
    --pylint  Enables pylint
    --picked  Checks only git changed files
    --help    Show this message and exit.

