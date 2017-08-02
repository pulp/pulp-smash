Installation
============

Location: :doc:`/index` → :doc:`/installation`

Installing Pulp Smash into a virtual environment [1]_ is recommended. To create
and activate a virtual environment:

.. code-block:: sh

    python3 -m venv env
    source env/bin/activate  # run `deactivate` to exit environment

Pulp Smash can be installed from PyPI or from source. To install from `PyPI`_:

.. code-block:: sh

    pip install pulp-smash  # prepend `python -m` on Python 3.3

To install Pulp Smash from source (`GitHub`_):

.. code-block:: sh

    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    pip install .

Pulp Smash can also be installed from source in "develop mode," where changes to
source code are reflected in the working environment. The ``--editable`` flag
does this. Also, development dependencies can be installed by requiring the
extra "dev" group.

.. code-block:: sh

    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    pip install --editable .[dev]

For an explanation of key concepts and more installation strategies, see
`Installing Python Modules`_.

.. [1] See `Virtual Environments and Packages`_ for an explanation of virtual
    environments. ``python3 -m venv`` and ``virtualenv`` are similar, but the
    former ships with Python as of Python 3.3, whereas the latter is a third
    party tool.

.. _GitHub: https://github.com/PulpQE/pulp-smash
.. _Installing Python Modules: https://docs.python.org/3/installing/
.. _PyPI: https://pypi.python.org/pypi/pulp-smash
.. _Virtual Environments and Packages: https://docs.python.org/3/tutorial/venv.html
