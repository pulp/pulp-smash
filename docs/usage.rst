Usage
=====

Location: :doc:`/index` → :doc:`/usage`

Configuring Pulp Smash
----------------------

Pulp Smash needs a configuration file to be present in order to know how to
access the Pulp application under test. To do that you can use the following
command::

    pulp-smash settings create

You will be prompted for information like the version of Pulp, API credentials,
whether the API is accessible via HTTPS, and so on. It is assumed that both
Pulp's CLI client and Pulp's alternate download policies are installed and
configured.

.. note::

    For information on how to install and configure Pulp (not Pulp Smash!), see
    the `Pulp installation`_ documentation.

If you are planning to test a clustered Pulp application, then you are going to
need to manually edit the settings file. Before getting into the details of the
settings file, let's see how Pulp Smash finds the settings file.

Pulp Smash abides by the `XDG Base Directory Specification`_. By default, Pulp
Smash searches for a configuration file named ``settings.json``, within a
directory named ``pulp_smash``, within any of the ``$XDG_CONFIG_DIRS``. In
practice, this typically means that the configuration file exists at
``~/.config/pulp_smash/settings.json``.

``$XDG_CONFIG_DIRS`` is a precedence-ordered list. If multiple configuration
files reside on the file system, the first file found is used. Settings are not
cascaded.

To search for a file named something other than ``settings.json``, set the
``PULP_SMASH_CONFIG_FILE`` environment variable. It should be a file name, not a
path. For example:

.. code-block:: sh

    # Valid. Search paths such as: ~/.config/pulp_smash/alternate-settings.json
    PULP_SMASH_CONFIG_FILE=alternate-settings.json \
      python3 -m unittest discover pulp_smash.tests

    # Invalid. Results are undefined.
    PULP_SMASH_CONFIG_FILE=foo/alternate-settings.json \
      python3 -m unittest discover pulp_smash.tests

Now that how Pulp Smash finds the settings file is known, let's know how the
configuration file format is. Consider the example below:

.. code-block:: json

    {
        "pulp": {
            "auth": ["username", "password"],
            "version": "2.12.2",
            "selinux enable": true
        },
        "hosts": [
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

A single Pulp application may be deployed on just one host or on several hosts.
The configuration file above describes the former case. The "pulp" section lets
you declare properties of the entire Pulp application. The "hosts" section lets
you declare properties of the individual hosts that comprise the Pulp
application.

Each host must fulfill the "shell" role. In addition, the hosts must
collectively fulfill the :obj:`pulp_smash.config.REQUIRED_ROLES`.

Not all roles requires additional information. Currently, only the ``amqp
broker``, ``api`` and ``shell`` roles do. The ``amqp broker`` object must have a
``service`` key set to either ``qpidd`` or ``rabbitmq``. The ``api`` role means
that ``httpd`` will be running on the host. Its ``scheme`` key specifies whether
the API should be accessed over HTTP or HTTPS, and its ``verify`` key specifies
whether and how SSL certificates should be verified. (It may be true, false, or
a path to a custom certificate file. In the latter case, the certificate must be
on the Pulp Smash host.) The ``shell`` role specifies whether to access the host
using a ``local`` shell or over ``ssh``.

.. note::

    Pulp Smash can access a host via SSH only if the SSH connection can be made
    without typing a password. Make sure to configure SSH so just running ``ssh
    $hostname`` will access the host. See sshd_config(5).

The example below shows a configuration file that enables Pulp Smash to access a
clustered Pulp deployment:

.. code-block:: json

    {
        "pulp": {
            "auth": ["username", "password"],
            "version": "2.12.1",
            "selinux enable": true
        },
        "hosts": [
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
first host and that the Pulp related roles plus the ``squid`` are available
on both. The example shows how to have a clustered deployment where second
host will connect to the first host's ``mongod`` and ``amqp broker``, all
the other services will work as a failover redundancy. Like, if first host's
``pulp resource manager`` goes down than Pulp failover feature will activate
and start using the second host's ``pulp resource manager``.

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

.. _Pulp installation:
    http://docs.pulpproject.org/user-guide/installation/index.html
.. _XDG Base Directory Specification:
    https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
