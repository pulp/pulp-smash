About
=====

Location: :doc:`/index` → :doc:`/about`

Why does Pulp Smash exist? What are its goals, and what does it *not* do?

.. contents::
    :local:

Why Pulp Smash?
---------------

Pulp Smash exists to make automated functional testing of Pulp easier.

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
you care about the state of the target system. Pulp Smash makes it easy to do
the following and more:

* Drop databases.
* Forcefully delete files from the filesystem.
* Stop and start system services.

Pulp Smash treats the system(s) under test as cattle, not pets. [3]_

Contributing
------------

Contributions are encouraged. The easiest way to contribute is to submit a pull
request on GitHub, but patches are welcome no matter how they arrive.

In a Python 3 virtual environment, in the root of Pulp Smash dir run the
following command:

.. code-block:: shell   

    make install-dev

This command will install Pulp Smash in developer mode and it will install
all the required dependencies.
Also, it will create a `pre-commit hook` to run the code formatting, and
linters - the command `git commit` will trigger the `pre-commit` to run.

Learning Pulp Smash
~~~~~~~~~~~~~~~~~~~

Not sure where to start? Consider reading some existing tests in `Pulp 2
Tests`_.

Pulp Smash Interactive Console
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The command ``pulp-smash shell`` opens an interactive Python console with Pulp-Smash
most common used objects already imported in to the context.

The configuration for the shell is read from 
``XDG HOME`` usually ``~/.config/pulp_smash/settings.json`` 
optionally it is possible to set on env ``export PULP_SMASH_CONFIG_FILE=/path/to/settings.json`` 
or by passing it to the command line as in ``pulp-smash shell --config ~/path/to/settings.json``

.. raw:: html

    <script id="asciicast-235178" src="https://asciinema.org/a/235178.js" async></script>
    <a href="https://asciinema.org/a/235178">https://asciinema.org/a/235178</a>

Code Standards
~~~~~~~~~~~~~~

Please adhere to the following guidelines:

* Code should be compliant with `PEP-8`_.
* Code should follow the `Black`_ code style with a line length of 79 characters.
* Pull requests must pass the `Travis CI`_ continuous integration tests. You can
  locally verify your changes before submitting a pull request by executing
  ``make all``.
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

In addition, code should adhere as closely as reasonably possible to the
existing style in the code base. A consistent style makes it possible to focus
on the substance of code, rather than its form.

Review Process
~~~~~~~~~~~~~~

Changes that meet the `code standards`_ will be reviewed by a Pulp Smash
developer and are likely to be merged.

Though commits are accepted as-is, they are frequently accompanied by a
follow-up commit in which the reviewer makes a variety of changes, ranging from
simple typo corrections and formatting adjustments to whole-sale restructuring
of tests. This can take quite a bit of effort and time. If you'd like to make
the review process faster and have more assurance your changes are being
accepted with little to no modifications, take the time to really make your
changes shine: ensure your code is DRY, matches existing formatting conventions,
is organized into easy-to-read blocks, has isolated unit test assertions, and so
on.

Join the #pulp IRC channel on `freenode`_ if you have further questions.

Labels
~~~~~~

Issues are categorized with `labels`_. Pull requests are categorized with
GitHub's `pull request reviews`_ feature.

The specific meaning of (issue) labels is as follows.

Issue Type: Bug
    This label denotes an issue that describes a specific counter-productive
    behaviour. For example, an issue entitled "test X contains an incorrect
    assertion" is a great candidate for this label.

Issue Type: Discussion
    This label denotes an issue that broadly discusses some topic. Feature
    requests should be given this label. If a discussion results in a specific
    and concrete plan of action, a new issue should be opened, where that issue
    outlines a specific solution and has a label of "Issue Type: Plan".

Issue Type: Plan
    This label denotes an issue that outlines a specific, concrete
    plan of action for improving Pulp Smash. This may include plans for new
    utilities or refactors of existing tests or other tools. Open-ended
    discussions (including feature requests) should go into issues labeled
    "Issue Type:Discussion."

Issue Type: Test Case
    This label indicates that an issue is asking for a test case to be
    automated. (Issues with this label are a special type of plan.)

   .. warning::
      This label was kept here for historical reasons. Test cases for Pulp 2 or
      Pulp 3 should not be filed on Pulp Smash anymore.
      See: `creating issues`_


Creating issues
~~~~~~~~~~~~~~~

1 - *Pulp Smash Issues*

  Issues related to Pulp-Smash itself should be filed on `Pulp Smash issues`_.

2 - *Pulp 2 and Pulp 3 Issues*

   As an effort to simplify where issues were tracked, Pulp 2 and Pulp 3 issues
   are being tracked on `pulp.plan.io`_ for the sake of simplicity.

   A new tracker type ``Test`` was created. Test cases should be related to the
   parent issue so they can be worked and groomed separately, if applicable.

   Select the proper fields to distinguish Pulp versions, and so on.

   To illustrate: `test case`_.

   .. warning::
      On `pulp.plan.io`_ the field `Smash Test` was kept for historical reasons. It
      should not be used anymore.

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

.. _Black: https://github.com/ambv/black
.. _GNU Make: https://www.gnu.org/software/make/
.. _OpenSSH: http://www.openssh.com/
.. _PEP-8: https://www.python.org/dev/peps/pep-0008
.. _Pulp 2 Tests: https://github.com/PulpQE/pulp-2-tests
.. _Pulp Smash issues: https://github.com/PulpQE/pulp-smash/issues
.. _Travis CI: https://travis-ci.org/PulpQE/pulp-smash
.. _XDG Base Directory Specification: http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
.. _freenode: https://freenode.net/
.. _good commit messages: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
.. _labels: https://github.com/PulpQE/pulp-smash/labels
.. _pull request reviews: https://help.github.com/articles/about-pull-request-reviews/
.. _pulp.plan.io: https://pulp.plan.io/
.. _rewrite history: https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History
.. _test case: https://pulp.plan.io/issues/4035