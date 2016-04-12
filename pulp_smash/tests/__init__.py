# coding=utf-8
# flake8:noqa
"""Tests for Pulp.

This package and its sub-packages contain functional tests for Pulp. These
tests should be run against live Pulp systems. These tests may target all of
the different interfaces exposed by Pulp, including its API and CLI. These
tests are entirely different from the unit tests in :mod:`tests`.

A given Pulp server may have an arbitrary set of plugins installed. As a
result, not all of the tests in Pulp Smash should be run against a given Pulp
server. Consequently, tests are organized on a per-plugin basis. Tests for the
Docker plugin are in :mod:`pulp_smash.tests.docker`, tests for the OSTree
plugin are in :mod:`pulp_smash.tests.ostree`, and so on. Several other factors
also determine whether a test should be run, such as whether a given bug has
been fixed in the version of Pulp under test. However, plugins are the broadest
determinant of which tests should be run, so they direct the test suite
structure.

Selecting and deselecting tests is a common task, and module
:mod:`pulp_smash.selectors` has a collection of tools for this problem area. At
a minimum, *every* ``test*`` module should define a `setUpModule`_ function
that checks for the presence of needed Pulp plugins and raises a `SkipTest`_
exception if needed. For convenience, functions such as
:func:`pulp_smash.tests.docker.utils.set_up_module` can be used for this
purpose. For example::

    >>> from pulp_smash.tests.docker.utils import set_up_module as setUpModule

-----

By default, Requests refuses to make insecure HTTPS connections. You can
override this behaviour by passing ``verify=False``. For example::

    requests.get('https://insecure.example.com', verify=False)

If you do this, Requests will make the connection. However, an
``InsecureRequestWarning`` is still raised. This is problematic. If a user has
explicitly stated that they want insecure HTTPS connections and they are
pestered about that fact, the user is effectively trained to ignore warnings.

Thus, when this module is imported, it suppresses
``requests.packages.urllib3.exceptions.InsecureRequestWarning``. This filtering
does not affect whether SSL verification is performed. If an insecure
connection is attempted and ``verify=True`` or is unspecified, the connection
is not made.

.. NOTE:: The ``InsecureRequestWarning`` suppression is process-wide.

Unfortunately, Python's warnings and filter system is process-wide. Imagine an
application which uses both Pulp Smash and some other library, and imagine that
the other library generates ``InsecureRequestWarning`` warnings. The warnings
raised by that application are suppressed by the filter created here. The
``warnings.catch_warnings`` context manager is not a good solution to this
problem, as it is thread-unsafe.

.. _SkipTest: https://docs.python.org/3.5/library/unittest.html#unittest.SkipTest
.. _setUpModule: https://docs.python.org/3.5/library/unittest.html#setupmodule-and-teardownmodule
"""
from __future__ import unicode_literals

from warnings import simplefilter

import requests

simplefilter(
    'ignore',
    requests.packages.urllib3.exceptions.InsecureRequestWarning,
)
