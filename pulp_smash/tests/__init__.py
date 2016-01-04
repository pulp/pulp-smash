# coding=utf-8
"""Tests for Pulp.

This package and its sub-packages contain tests for Pulp. These tests should be
run against live Pulp systems. These tests may target all of the different
interfaces exposed by Pulp, including its API and CLI.

These tests are entirely different from the tests in :mod:`tests`.

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
"""
from __future__ import unicode_literals

from warnings import simplefilter

import requests

simplefilter(
    'ignore',
    requests.packages.urllib3.exceptions.InsecureRequestWarning,
)
