Pulp Smash
==========

.. image:: https://coveralls.io/repos/github/PulpQE/pulp-smash/badge.svg?branch=master
    :target: https://coveralls.io/github/PulpQE/pulp-smash?branch=master

Pulp Smash is a test suite for `Pulp`_. It lets you execute a workflow like
this:

.. code-block:: sh

    pip install pulp-smash
    python -m pulp_smash  # follow the instructions

Pulp Smash is a GPL-licensed Python library, but no knowledge of Python is
required to execute the tests. Just install the application, run it, and follow
the prompts.

.. _Pulp: http://www.pulpproject.org/

.. All text above this comment should also be in docs/index.rst, word for word.

The `full documentation <http://pulp-smash.readthedocs.io/en/latest/>`_ is
available on ReadTheDocs. It can also be generated locally:

.. code-block:: sh

    virtualenv env && source env/bin/activate
    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    pip install -r requirements.txt -r requirements-dev.txt
    make docs-html
