Installation
============

Location: :doc:`/index` → :doc:`/installation`

There are several different ways to install Python packages, and Pulp Smash
supports some of the most common methods. For example, a developer might want to
install Pulp Smash in editable mode into a virtualenv:

.. code-block:: sh

    python3 -m venv ~/.venvs/pulp-smash
    source env/bin/activate  # run `deactivate` to exit environment
    pip install --upgrade pip
    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    pip install --editable .[dev]
    make all  # verify sanity

For an explanation of key concepts and more installation strategies, see
`Installing Python Modules`_. For an explanation of virtualenvs, see `Virtual
Environments and Packages`_.

In addition to the dependencies listed in ``setup.py``, install OpenSSH if
testing is to be performed against a remote host. [1]_

.. [1] This hard dependency is a bug. It would be better to require _an_ SSH
    implementation, whether provided by OpenSSH, Paramiko, Dropbear, or
    something else.

.. _Installing Python Modules: https://docs.python.org/3/installing/
.. _Virtual Environments and Packages: https://docs.python.org/3/tutorial/venv.html
