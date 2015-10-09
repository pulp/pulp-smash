Installation
============

Location: :doc:`/index` → :doc:`/installation`

There are several ways to install Pulp Smash.

.. contents::
    :local:

From Source
-----------

This is the most universal installation procedure, but it is also the most
kludgy. You must install updates yourself, and you may need to deal with
dependency hell. To install from source:

1. Download a copy of the Pulp Smash source code. There are several ways to get
   the source code:

   * Visit the `Pulp Smash GitHub page`_ and click on the "Download ZIP" button.
     Extract the archive.
   * Execute ``git clone https://github.com/PulpQE/pulp-smash.git``.

2. Execute ``python setup.py install``.

Pulp Smash's dependencies are listed in ``setup.py``. Look for the
``install_requires`` section.

Pip
---

If you use Pip, you will be lifted out of dependency hell. However, updating is
left to you, and installing Pip may be a challenge depending on your platform.
If Pip is already available, installing Pulp Smash is as simple as::

    pip install pulp-smash

Or::

    pip install git+https://github.com/PulpQE/pulp-smash.git#egg=pulp-smash

The former will install the current stable version from PyPi, and the latter
will install the current development version directly from source. There are
many more use cases for Pip, and they are covered in the Python Packaging User
Guide section entitled `Installing Packages`_.

Other
-----

The installation strategies listed above assume that you'd like to install Pulp
Smash system-wide. However, it's possible to install in a more targeted manner.
For example, you can install a package only for the current user::

    wget https://github.com/PulpQE/pulp-smash/archive/master.zip
    unzip master.zip
    cd pulp-smash-master
    python setup.py install --user --record files.txt

This records the installed files in ``files.txt``. You can uninstall the package
by manually removing the files.

A second option is to create a `virtualenv`_::

    python -m virtualenv env
    source env/bin/activate
    pip install git+https://github.com/PulpQE/pulp-smash.git#egg=pulp-smash

If you are using a version of Python older than 3.4, you must install virtualenv
separately. In that case, the first command changes to ``virtualenv env``.

If you *do* want to install system-wide, then all of the strategies listed above
are non-optimal, as you will not receive automatic updates. A better solution is
to install a package using your system package manager. (yum, apt-get, pacman,
emerge, etc) At present, no packages are known to exist. If you create a
package, please get in touch (#pulp on `freenode`_)!

.. _Installing Packages: https://packaging.python.org/en/latest/installing/
.. _Pulp Smash GitHub page: https://github.com/PulpQE/pulp-smash
.. _freenode: https://freenode.net/
.. _virtualenv: http://virtualenv.readthedocs.org/en/latest/
