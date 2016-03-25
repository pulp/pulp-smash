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
* `GNU Make`_ (or a compatible clone),
* and the `XDG Base Directory Specification`_.

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

* Pull requests should pass continuous integration steps. You can verify your
  change(s) locally by executing ``make all``.
* If adding a new test for Pulp, please run the test and communicate the
  results in the commit message or as a pull request comment.
* Adhere to typical commit guidelines:

    * Commits should be small and coherent. One commit should address one issue.
      Ask yourself: "can I revert this commit?"
    * Commits should have `good commit messages`_.
    * `Rebasing`_ is encouraged. Rebasing produces a much nicer commit history
      than merging.

* When in doubt, ask on IRC. Join the #pulp channel on `freenode`_.

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

.. _GNU Make: https://www.gnu.org/software/make/
.. _Rebasing: http://www.git-scm.com/book/en/v2/Git-Branching-Rebasing
.. _XDG Base Directory Specification: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
.. _freenode: https://freenode.net/
.. _good commit messages: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
