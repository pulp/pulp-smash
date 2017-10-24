# coding=utf-8
# flake8:noqa
"""Tests for Pulp.

This package contain functional tests for Pulp. These tests should be run
against live Pulp systems. These tests may target all of the different
interfaces exposed by Pulp, including its API and CLI. These tests are entirely
different from the unit tests in :mod:`tests`, which test Pulp Smash itself.

The tests are organized into a hierarchy in the following form:
``major_pulp_version.plugin.interface``. For example, Pulp 2 tests for the RPM
plugin's API interface are in :mod:`pulp_smash.tests.pulp2.ostree.api_v2`.

There are several factors that determine whether or not a given test should
run. These factors include:

* Which version of Pulp is under test? For example, version 2.13.2, 2.14.1, 3,
  and so on.
* Given that a certain version of Pulp is under test, which bugs affect that
  Pulp installation? For example, does `<https://pulp.plan.io/issues/2144>`_
  affect the Pulp installation under test?
* Which plugins are installed? For example, docker, ostree, puppet, and so on.

These are all common reasons that a given test might be skipped. From a user's
perspective, this is all automatic. They need only install Pulp Smash,
configure it, and point a test runner at :mod:`pulp_smash.tests`.

From a Pulp Smash developer's perspective, some work needs to be done to make
this happen. There are two especially common ways to make this happen. First,
bug-specific skipping logic can be implemented with the methods in
:mod:`pulp_smash.selectors`, especially
:func:`pulp_smash.selectors.bug_is_testable` and it's sibling. Second, a
`setUpModule`_ function must be present in **every** ``test*`` module. In the
simplest case, this can be done with pre-defined functions. For example,
:mod:`pulp_smash.tests.pulp2.rpm.api_v2.test_broker` might do the following:

.. code-block:: python

    from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule

-----

By default, Requests refuses to make insecure HTTPS connections. You can
override this behaviour by passing ``verify=False``. For example::

    requests.get('https://insecure.example.com', verify=False)

If you do this, Requests will make the connection. However, an
``InsecureRequestWarning`` will be raised. This is problematic. If a user has
explicitly stated that they want insecure HTTPS connections and they are
pestered about that fact, the user is effectively trained to ignore warnings.

This module attempts to solve that problem. When this module is imported, a
filter is prepended to the warning module's list of filters. The filter states
that ``InsecureRequestWarning`` warnings should be ignored. Note that this has
no effect on whether SSL verification is performed. Insecure HTTPS connections
are still blocked by default. The filter only has an effect on whether
``InsecureRequestWarning`` messages are displayed.

This filtering has a drawback: the warning module's filtering system is
process-wide. Imagine an application which uses both Pulp Smash and some other
library, and imagine that the other library generates
``InsecureRequestWarning`` warnings. The filter created here will suppress the
warnings raised by that application. The ``warnings.catch_warnings`` context
manager is not a good solution to this problem, as it is thread-unsafe.

This filtering is also limited: any Python code which executes after this
module is imported can also manipulate the warning module's list of filters,
and can therefore override the effects of this module. Unfortunately, the
unittest test runner from the standard library does just that. As of this
writing (with Python 3.5.3), the following filter (among others) is prepended
to the warning module's filter list whenever a test case is executed:

    >>> from warnings import filters
    >>> filters[1]
    ('default', None, <class 'Warning'>, None, 0)

This filter matches all warnings — including ``InsecureRequestWarning`` — and
causes them to be emitted. In theory, this does not occur if ``-W
'ignore::requests.packages.urllib3.exceptions.InsecureRequestWarning'`` is
passed when calling ``python -m unittest``. A more efficacious solution is to
use a different test runner.

.. _setUpModule: https://docs.python.org/3/library/unittest.html#setupmodule-and-teardownmodule
"""
from warnings import simplefilter

import urllib3

simplefilter(
    'ignore',
    urllib3.exceptions.InsecureRequestWarning,
)
