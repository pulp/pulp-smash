# coding=utf-8
"""Test the API's `authentication`_ functionality.

.. _authentication:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/authentication.html
"""
# Why The Comments?
# =================
#
# This module serves as an introduction to Pulp Smash. This module was picked
# because it's one of the simplest in the test suite. A "how to understand Pulp
# Smash tests" section in the documentation should link to this module.
#
# Encoding
# --------
#
# The encoding declaration at the beginning of this file tells Python which
# encoding scheme was used when creating this document, and therefore how to
# decode the bytes in this document. If omitted, Python might use an UTF-8
# decoder, or a utf-8 decoder, or something else, and that can be problematic.
# Try running this script with Python in a variety of environments:
#
#     #!/usr/bin/env python3
#     # …
#     import sys
#     print(sys.getdefaultencoding())
#
# Shebang
# -------
#
# There is no shebang at the top of this file. That's because this file is not
# meant to be executed directly. Instead, a "test runner" program will import
# this module, and it will decide if and how to execute the code herein.
# Several test runners can run Pulp Smash tests, but with varying degrees of
# compatibility. The "unittest" test runner is best supported. [1]
#
# Docstrings
# ----------
#
# The docstrings throughout this module comply with reStructuredText syntax.
# [2] However, a tool like `rst2html` cannot extract and compile the docstrings
# from this file. Instead, the Sphinx documentation generator must be used. [3]
# It knows how to extract docstrings, and it knows how to treat directives like
# the `:meth:` directive. See the README file in the root of this repository
# for more information.
#
# Package Structure
# -----------------
#
# Why is this module placed where it is?
#
# First, a path such as `pulp_smash.tests.platform.api_v2.test_login` is
# human-readable. This module of Pulp Smash tests relies on the base platform's
# API version 2 interface, and it tests logging in.
#
# Second, Pulp has a plug-in architecture, where the base platform is always
# present, and everything else is optional. Pulp Smash's packages are
# structured to reflect that plug-in architecture. This makes it easy for a
# test case to know which plug-ins it may reference. For example, test cases in
# `pulp_smash.tests.rpm` may reference the RPM plug-in, but must not reference
# the Puppet plugin. This also makes it easier to automatically skip tests. For
# example, if the RPM plug-in is not installed on the Pulp system under test,
# all test cases in `pulp_smash.tests.rpm` are skipped.
#
# No per-plugin test skipping logic is present in this module. Elsewhere, be on
# the look-out for `setUpModule` functions and mentions of the `load_tests`
# protocol. [4]
#
# Imports
# -------
#
# The imports are listed in the order recommended by PEP 8: double-underscore,
# standard library, third party and local. [5][6] In addition, blocks of
# imports are sorted alphabetically, and "import x" statements are placed
# before "from x import y" statements.
#
# [1] https://docs.python.org/3.5/library/unittest.html
# [2] http://docutils.sourceforge.net/docs/user/rst/quickstart.html
# [3] http://www.sphinx-doc.org/en/stable/
# [4] https://docs.python.org/3/library/unittest.html#load-tests-protocol
# [5] https://www.python.org/dev/peps/pep-0008/#imports
# [6] https://docs.python.org/3/library/__future__.html
import unittest

from pulp_smash import api, config, selectors
from pulp_smash.constants import ERROR_KEYS, LOGIN_KEYS, LOGIN_PATH


class LoginTestCase(unittest.TestCase):
    """Tests for logging in."""

    # The `TestCase` class provides a lot of functionality, and it's a Good
    # Idea to read the unittest documentation. [1] Right now, you just need to
    # know that, when a test runner executes a `TestCase` class:
    #
    # * The `test*` methods run in alphabetic order.
    # * A failure in one `test*` method doesn't affect any other `test*`
    #   method.
    #
    # [1] https://docs.python.org/3/library/unittest.html

    def test_success(self):
        """Successfully log in to the server.

        Assert that:

        * The response has an HTTP 200 status code.
        * The response body is valid JSON and has correct keys.
        """
        # The object returned by `config.get_config()` tells the new `Client`
        # object where the Pulp server is, what the authentication credentials
        # are, and so on.
        #
        # There are several assertions that can be made about the login API
        # call. Rather than logging in logging in once for every test, we log
        # in just once, and make multiple assertions about that log in.
        response = api.Client(config.get_config()).post(LOGIN_PATH)
        with self.subTest(comment='check response status code'):
            self.assertEqual(response.status_code, 200)
        with self.subTest(comment='check response body'):
            self.assertEqual(frozenset(response.json().keys()), LOGIN_KEYS)

    def test_failure(self):
        """Unsuccessfully log in to the server.

        Assert that:

        * The response has an HTTP 401 status code.
        * The response body is valid JSON and has correct keys.
        """
        # By default, `Client` objects munge every response they receive. They
        # act cautiously, and do things like raise an exception if the response
        # has an HTTP 4XX or 5XX status code. We don't want that to happen in
        # this test case. So, we pass the `Client` object a non-default
        # function with which to munge responses. In addition, we override the
        # default authentication handling for just this one API call.
        #
        # The API and CLI clients are interesting and capable classes. Read
        # about them.
        cfg = config.get_config()
        response = (
            api.Client(cfg, api.echo_handler).post(LOGIN_PATH, auth=('', ''))
        )
        with self.subTest(comment='check response status code'):
            self.assertEqual(response.status_code, 401)
        # The `version` attribute should correspond to the version of the Pulp
        # server under test. This block of code says "if bug 1412 is not fixed
        # in Pulp version X, then skip this test."
        if selectors.bug_is_testable(1412, cfg.version):
            with self.subTest(comment='check response body'):
                self.assertEqual(frozenset(response.json().keys()), ERROR_KEYS)
