# coding=utf-8
"""Tests for Pulp.

This package contain functional tests for Pulp. These tests should be run
against live Pulp systems. These tests may target all of the different
interfaces exposed by Pulp, including its API and CLI. These tests are entirely
different from the unit tests in :mod:`tests`, which test Pulp Smash itself.

These tests are currently being moved out of Pulp Smash. The tools used by the
tests will remain.

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
