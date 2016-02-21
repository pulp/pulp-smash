Pulp Smash
==========

.. image:: https://coveralls.io/repos/PulpQE/pulp-smash/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/PulpQE/pulp-smash?branch=master

Pulp Smash is a test suite for `Pulp`_. It lets you execute a workflow like
this::

    pip install pulp-smash
    python -m pulp_smash  # follow the instructions

Pulp Smash is a GPL-licensed Python library, but no knowledge of Python is
required to execute the tests. Just install the application, run it, and follow
the prompts.

.. _Pulp: http://www.pulpproject.org/

.. Everything above this comment should also be in docs/index.rst, word for
   word.

The `full documentation <http://pulp-smash.readthedocs.org/en/latest/>`_ is
available on ReadTheDocs. It can also be generated locally::

    virtualenv env && source env/bin/activate
    git clone https://github.com/PulpQE/pulp-smash.git
    cd pulp-smash
    pip install -r requirements.txt -r requirements-dev.txt
    make docs-html
