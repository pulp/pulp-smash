About
=====

Location: :doc:`/index` → :doc:`/about`

Why does Pulp Smash exist? What are its goals, and what does it *not* do?

.. contents::
    :local:

Why Pulp Smash?
---------------

Pulp Smash exists to make testing Pulp easy. It supersedes `Pulp Automation`_.
Why greenfield a new library instead of improving the existing one? Because
there are significant issues with the existing library. To name a few:

* Pulp Automation can only be installed and used on a limited set of systems. It
  includes hard-coded references to system-wide directories and files including:

  * ``/usr/bin/pulp-consumer``
  * ``/usr/lib/python2.7/site-packages``
  * ``/usr/local/bin/geninventory``
  * ``/usr/share/pulp_auto``

  It also includes references to system-specific tools such as ``yum``.
* The installer script places files in system-wide locations. This is something
  that only a system package manager should do.
* Pulp Automation only works with Python 2.7. The hard-coded references to
  ``/usr/lib/python2.7/site-packages`` indicate that expanding compatibility is
  a difficult task.
* Many tests need to be re-written from scratch. Compare
  :mod:`pulp_smash.tests.test_login` with the equivalent module in Pulp
  Automation, `tests.general_tests.test_01_log_in`_.
* The existing code is simply poor quality. Pylint complains about thirteen
  unique issues when run against `pulp_auto.repo`_, including redefined
  builtins, dangerous default values, unused arguments and missing docstrings.
* Pulp Automation suffers from feature creep. It includes code for working with
  Ansible, EC2, Docker and Jenkins.

In light of the issues listed above, green-fielding seems appropriate.

Scope and Limitations
---------------------

This is a list of goals that 

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

Should Pulp Smash record all changes it makes to a remote system and revert them
when testing is complete, or should systems be treated as throw-away? In other
words, should the systems under test be treated like pets or cattle? [3]_ This
has yet to be decided.

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
.. _Pulp Automation: https://github.com/RedHatQE/pulp-automation
.. _XDG Base Directory Specification: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
.. _pulp_auto.repo: https://github.com/RedHatQE/pulp-automation/blob/master/pulp_auto/repo.py
.. _tests.general_tests.test_01_log_in: https://github.com/RedHatQE/pulp-automation/blob/master/tests/general_tests/test_01_log_in.py
