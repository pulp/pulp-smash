About
=====

Location: :doc:`/index` → :doc:`/about`

Why does Pulp Smash exist? What are its goals, and what does it *not* do?

.. contents::
    :local:

Why Pulp Smash?
---------------

Pulp Smash exists to make testing Pulp easy.

Scope and Limitations
---------------------

Portability
~~~~~~~~~~~

Pulp Smash should be usable in any environment that supports:

* one of the Python versions listed in ``.travis.yml``,
* the dependencies listed in ``setup.py``,
* a \*nix-like shell,
* the `XDG Base Directory Specification`_,
* and `OpenSSH`_ or a compatible clone.

In addition, we recommend that `GNU Make`_ or a compatible clone be available.

This level of portability [1]_ allows Pulp Smash to be accessible [2]_.

Provisioning
~~~~~~~~~~~~

Pulp Smash is not concerned with provisioning systems. Users must bring their
own systems.

Destructiveness
~~~~~~~~~~~~~~~

*Pulp Smash is highly destructive!* You should not use Pulp Smash for testing if
you care about the state of the target system. Pulp Smash will do the following
to a system under test, and possibly more:

* It will drop databases.
* It will forcefully delete files from the filesystem.
* It will stop and start system services.

Pulp Smash treats the system(s) under test as cattle, not pets. [3]_

Contributing
------------

Contributions are encouraged. The easiest way to contribute is to submit a pull
request on GitHub, but patches are welcome no matter how they arrive.

A strategy for creating a development environment is listed in
:doc:`/installation`. To verify the sanity of your development environment,
``cd`` into the Pulp Smash source code directory and execute ``make all``.

Please adhere to the following guidelines:

* Pull requests must pass the `Travis CI`_ continuous integration tests. These
  tests are automatically run whenever a pull request is submitted. If you want
  to locally verify your changes before submitting a pull request, execute
  ``make all``.
* Test failures must not be introduced. Consider running all new and modified
  tests and copy-pasting the output from the test run as a comment in the GitHub
  pull request. The simplest way to run the test suite is with ``python -m
  unittest2 pulp_smash.tests``. See the unittest `Command-Line Interface`_ and
  ``python -m pulp_smash`` for more information.
* Each commit in a pull request must be atomic and address a single issue. Try
  asking yourself: "can I revert this commit?" Knowing how to `rewrite history`_
  may help. In addition, please take the time to write a `good
  <http://stopwritingramblingcommitmessages.com/>`_ `commit
  <https://robots.thoughtbot.com/5-useful-tips-for-a-better-commit-message>`_
  `message <http://chris.beams.io/posts/git-commit/>`_. While not *strictly*
  necessary, consider: commits are (nearly) immutable, and getting commit
  messages right makes for a more pleasant review process, better release notes,
  and easier use of tools like ``git log``, ``git blame`` or ``git bisect``.
* The pull request must not raise any other outstanding concerns. For example,
  do not author a commit that adds a 10MB binary blob without exceedingly good
  reason. As another example, do not add a test that makes dozens of concurrent
  requests to a public service such as docker hub.

Your changes will eventually be reviewed and merged if they meet these
requirements. Join the #pulp IRC channel on `freenode`_ if you have further
questions.

Though commits are accepted as-is, they are frequently accompanied by a
follow-up commit in which the reviewer makes a variety of changes, ranging from
simple typo corrections and formatting adjustments to whole-sale restructuring
of tests. This can take quite a bit of effort and time. If you'd like to make
the review process faster and have more assurance your changes are being
accepted with little to no modifications, take the time to really make your
changes shine: ensure your code is DRY, matches existing formatting conventions,
is organized into easy-to-read blocks, has isolated unit test assertions, and so
on.

.. [1] Portable software cannot make assumptions about its environment. It
    cannot reference ``/etc/pki/tls/certs/ca-bundle.crt``  or call ``yum``.
    Instead, it must use standardized mechanisms for interacting with its
    environment. This separation of concerns should lead to an application with
    fewer responsibilities. Fewer responsibilities means fewer bugs and more
    focused developers.
.. [2] An inaccessible project is a dead project. Labeling a project "open
    source" and licensing it under a suitable terms does not change that fact.
    People have better things to do than bang their head against a wall.
.. [3] The "pets vs cattle" analogy is widely attributed to Bill Baker of
    Microsoft.

.. _Command-Line Interface: https://docs.python.org/3/library/unittest.html#command-line-interface
.. _GNU Make: https://www.gnu.org/software/make/
.. _OpenSSH: http://www.openssh.com/
.. _Travis CI: https://travis-ci.org/PulpQE/pulp-smash
.. _XDG Base Directory Specification: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
.. _freenode: https://freenode.net/
.. _good commit messages: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
.. _rewrite history: https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History
