Configuration
=============

Location: :doc:`/index` → :doc:`/configuration`

Pulp Smash needs a configuration file. This configuration file declares certain
information about the Pulp application under test.

Interactive Configuration
-------------------------

To interactively create a configuration file, use the CLI:

    pulp-smash settings create

You will be prompted for information like the version of Pulp, API credentials,
whether the API is accessible via HTTPS, and so on. It is assumed that both
Pulp's CLI client and Pulp's alternate download policies are installed and
configured.

.. note::

    For information on how to install and configure Pulp (not Pulp Smash!), see
    the `Pulp installation`_ documentation.

Manual Configuration
--------------------

The interactive configuration tool assumes that all of Pulp's components, such
as the webserver and squid, are installed on a single host. If you wish to tests
a Pulp application whose components are installed on multiple hosts, you must
install a custom configuration file.

Pulp Smash's configuration file may reside in one of several locations. The
easiest way to deal with this complication is to let Pulp Smash tell you where
you should create a configuration file:

.. code-block:: sh

    cat >"$(pulp-smash settings save-path)" <<EOF
    ...
    EOF
    pulp-smash settings validate

The ``save-path`` sub-command creates any necessary intermediate directories.

Configuration File Paths
------------------------

Pulp Smash abides by the `XDG Base Directory Specification`_. When loading a
configuration file, Pulp Smash searches for a file named ``settings.json``,
within a directory named ``pulp_smash``, within any of the ``$XDG_CONFIG_DIRS``.
In practice, this typically means that Pulp Smash loads
``~/.config/pulp_smash/settings.json``.

``$XDG_CONFIG_DIRS`` is a precedence-ordered list. If multiple configuration
files reside on the file system, the first file found is used. Settings are not
cascaded.

To search for a file named something other than ``settings.json``, set the
``PULP_SMASH_CONFIG_FILE`` environment variable. It should be a file name, not a
path. For example:

.. code-block:: sh

    # Valid. Search paths such as: ~/.config/pulp_smash/alt-settings.json
    PULP_SMASH_CONFIG_FILE=alt-settings.json pulp-smash settings load-path

    # Invalid. Results are undefined.
    PULP_SMASH_CONFIG_FILE=foo/alt-settings.json pulp-smash settings load-path

Pulp Smash abides by similar logic when saving a configuration to a file.

Configuration File Syntax
-------------------------

A configuration file is valid if:

* It adheres to the :data:`pulp_smash.config.JSON_CONFIG_SCHEMA` schema.
* Collectively, the hosts fulfill the
  :data:`pulp_smash.config.P2_REQUIRED_ROLES` or
  :data:`pulp_smash.config.P3_REQUIRED_ROLES` roles

These checks are executed by ``pulp-smash settings validate``.


A single Pulp application may be deployed on just one host or on several hosts.
The "pulp" section lets you declare properties of the entire Pulp application.
The "hosts" section lets you declare properties of the individual hosts that
host Pulp's components. Here's a sample configuration file:

.. code-block:: json

    {
      "pulp": {
        "version": "3",
        "auth": ["admin", "admin"],
        "selinux enabled": false
      },
      "hosts": [
        {
          "hostname": "pulp-1.example.com",
          "roles": {
            "api": {"scheme": "http", "service": "nginx"}
            "shell": {}
          }
        },
        {
          "hostname": "pulp-2.example.com",
          "roles": {
            "pulp resource manager": {},
            "pulp workers": {},
            "redis": {},
            "shell": {}
          }
        }
      ]
    }

In this example:

* The first host runs the nginx web server.
* The second host runs all other Pulp services, such as redis.
* Pulp Smash has shell access to both hosts.

The "shell" role deserves special mention. It has an optional "transport"
sub-key, e.g. ``"shell": {"transport": "..."}``:

* When set to "local," Pulp Smash will locally execute commands for that host
  with Python's built-in subprocess module
* When set to "ssh," Pulp Smash will execute commands over SSH.
* When omitted, Pulp Smash will guess how to execute commands by comparing the
  host's declared hostname against the current host's hostname. If the two
  hostnames are identical, Pulp Smash will behave as if "transport" is set to
  "local." Otherwise, Pulp Smash will behave as if "transport" is set to "ssh."

.. note::

    Pulp Smash can access a host via SSH only if the SSH connection can be made
    without typing a password. Make sure to configure SSH so just running ``ssh
    "$hostname"`` will access the host. See sshd_config(5).

.. _Pulp installation:
    http://docs.pulpproject.org/user-guide/installation/index.html
.. _XDG Base Directory Specification:
    https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
