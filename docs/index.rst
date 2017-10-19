Pulp Smash
==========

Pulp Smash is a test suite for `Pulp`_. It lets you execute a workflow like
this:

.. code-block:: sh

    pip install pulp-smash
    pulp-smash settings create  # generate a pulp2 settings file
    python3 -m unittest discover pulp_smash.pulp2.tests  # run the pulp2 tests


Pulp Smash is a GPL-licensed Python library, but no knowledge of Python is
required to execute the tests. Just install the application, run it, and follow
the prompts.

Pulp Smash has a presence on the following websites:

* `Documentation`_ is available on ReadTheDocs.
* A `Python package`_ is available on PyPi.
* `Source code`_ and the issue tracker are available on GitHub.

.. _Documentation: http://pulp-smash.readthedocs.io
.. _Pulp: http://www.pulpproject.org
.. _Python package: https://pypi.python.org/pypi/pulp-smash
.. _Source code: https://github.com/PulpQE/pulp-smash/

.. Everything above this comment should also be in the README, word for word.

Documentation contents:

.. toctree::
    :maxdepth: 2

    introductory-video
    installation
    usage
    about
    introductory-module
    api
