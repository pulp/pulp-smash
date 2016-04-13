Installation
============

Location: :doc:`/index` → :doc:`/installation`

Installing Pulp Smash into a virtual environment [1]_ is recommended. To create
and activate a virtual environment:

.. code-block:: sh

    pyvenv env  # or `virtualenv env` if using Python 2
    source env/bin/activate  # run `deactivate` to exit environment

To install Pulp Smash from `PyPi`_:

.. code-block:: sh

    pip install pulp-smash  # prepend `python -m` on Python 3.3

To install Pulp Smash from source (`GitHub`_):

.. code-block:: sh

    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    python setup.py install

To install Pulp Smash from source in "develop mode," where changes to source
files are reflected in the working environment:

.. code-block:: sh

    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    pip install -r requirements.txt -r requirements-dev.txt

For an explanation of key concepts and more installation strategies, see
`Installing Python Modules`_.

.. [1] See `Virtual Environments and Packages`_ for an explanation of virtual
    environments. If using Python 2, see `Virtualenv`_ instead. The ``pyvenv``
    and ``virtualenv`` tools are similar, but the former ships with Python as of
    Python 3.3, whereas the latter is a third party tool.

.. _GitHub: https://github.com/PulpQE/pulp-smash
.. _Installing Python Modules: https://docs.python.org/3/installing/
.. _PyPi: https://pypi.python.org/pypi/pulp-smash
.. _Virtual Environments and Packages: https://docs.python.org/3/tutorial/venv.html
.. _Virtualenv: http://virtualenv.readthedocs.org/en/latest/
