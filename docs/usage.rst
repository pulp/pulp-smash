Usage
=====

Location: :doc:`/index` → :doc:`/usage`

Configuring Pulp Smash
----------------------

Pulp Smash needs a configuration file to be present in order to know how to
access the Pulp system under test. To do that you can use the following
command::

    pulp-smash settings create

Provide the information like the authentication credentials for a Pulp admin
user, Pulp version, the system hostname, if the system is published under HTTPS
or not, etc.

The ``pulp-smash settings create`` command will generate a settings file for a
Pulp deployment. For more information about how to install Pulp check its
`installation docs`_. The generated settings file will assume that both Pulp's
Admin Client and Alternate Download Policies are installed and configured.

If you are planning to test a clustered Pulp deployment, then you are going to
need to manually edit the settings file. Before getting into the details of the
settings file, let's see how Pulp Smash finds the settings file.

Pulp Smash abides by the XDG Base Directory Specification. The configuration
file may be placed in any XDG-compliant location. The first configuration file
found is used. Settings are not cascaded.

.. note::

    The default settings filename is settings.json and it must be under a
    directory called pulp_smash. The pulp_smash directory may be placed in any
    XDG-compliant location.

A non-default configuration file can be selected with an environment variable
like so: ``PULP_SMASH_CONFIG_FILE=alternate-settings.json python3 -m unittest
discover pulp_smash.tests``. This variable should be a file name, not a path.

.. note::

    Setting ``PULP_SMASH_CONFIG_FILE`` will make Pulp Smash look for an
    alternate filename but the file must continue be placed under the
    pulp_smash directory on any XDG-compliant location.

Now that how Pulp Smash finds the settings file is known, let's know how the
configuration file format is. Consider the example below:

.. code-block:: json

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
    }

Pulp Smash's configuration file format allows configuring either a Pulp
deployment (as seen in the example above) or a clustered Pulp deployment where
each service can be installed on its own machine. The "pulp" section lets you
declare the version of and authentication credentials for the Pulp deployment
under test. The "systems" section provides information about each system that
composes the deployment. A system must have its hostname and the roles that
system has.

.. note::

    The only required role for a system is the ``shell`` role. Pulp Smash will not
    be able to test a Pulp deployment if any of the required roles are missing, see
    :obj:`pulp_smash.config.REQUIRED_ROLES` for the list of required roles.

Not all roles requires additional information. Currently, only the ``amqp
broker``, ``api`` and ``shell`` roles do. The ``amqp broker`` expects the
service to be defined and it can be either ``qpidd`` or ``rabbitmq``. The
``api`` role means that ``httpd`` will be running on the system. The api's
``scheme`` allows specifying if the API should be accessed using HTTP or HTTPS,
``verify`` allows specifying if the request SSL certificate should be verified
(true or false or a path to a custom certificate file, the path must be local
to the system where Pulp Smash is being run). The ``shell`` role configures how
the system will be accessed by using a ``local`` or ``ssh`` transport, only set
``local`` if Pulp Smash is running on that same system.

.. note::

    Pulp Smash can access a system via SSH only if the SSH connection can be
    made without typing a password. Make sure to configure SSH so just running
    ``ssh $hostname`` will access the system. See sshd_config(5).

The example below shows a configuration file that enables Pulp Smash to access
a clustered Pulp deployment:

.. code-block:: json

    {
        "pulp": {
            "auth": ["username", "password"],
            "version": "2.12.1"
        },
        "systems": [
            {
                "hostname": "first.example.com",
                "roles": {
                    "amqp broker": {"service": "qpidd"},
                    "api": {"scheme": "https", "verify": true},
                    "mongod": {},
                    "pulp cli": {},
                    "pulp celerybeat": {},
                    "pulp resource manager": {},
                    "pulp workers": {},
                    "shell": {"transport": "ssh"},
                    "squid": {}
                }
            },
            {
                "hostname": "second.example.com",
                "roles": {
                    "api": {"scheme": "https", "verify": false},
                    "pulp celerybeat": {},
                    "pulp resource manager": {},
                    "pulp workers": {},
                    "shell": {"transport": "ssh"},
                    "squid": {}
                }
            }
        ]
    }

Note that the roles ``mongod`` and ``amqp broker`` is only available on the
first system and that the Pulp related roles plus the ``squid`` are available
on both. The example shows how to have a clustered deployment where second
system will connect to the first system's ``mongod`` and ``amqp broker``, all
the other services will work as a failover redundancy. Like, if first system's
``pulp resource manager`` goes down than Pulp failover feature will activate
and start using the second system's ``pulp resource manager``.

Pulp Smash also has two other commands to help with configuration file
management: ``pulp-smash settings show`` and ``pulp-smash settings validate``
to show the current settings file and validate the settings file format schema
respectively. Those commands will take into consideration the environment
variables to select an alternate settings file.

Running the tests
-----------------

All tests can be run by running the command below::

    python3 -m unittest discover pulp_smash.tests

Any subset of tests may also be selected. For example, you may also run
``python3 -m unittest pulp_smash.tests.pulp2.platform.api_v2.test_login``.
Consult the unittest documentation for test selection syntax, and consult the
:doc:`/api` to see which test modules are available, check the tests under the
``pulp_smash.tests.*`` namespace.

.. _installation docs: http://docs.pulpproject.org/user-guide/installation/index.html
