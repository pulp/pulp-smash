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
from pulp_smash import api, selectors, utils
from pulp_smash.constants import ERROR_KEYS, LOGIN_KEYS, LOGIN_PATH


class LoginSuccessTestCase(utils.BaseAPITestCase):
    """Tests for successfully logging in."""

    # This test case has the following inheritance tree:
    #
    #     unittest.TestCase
    #     └── pulp_smash.utils.BaseAPITestCase
    #         └── pulp_smash.[…].LoginSuccessTestCase
    #
    # The `TestCase` class provides a lot of functionality, and it's a Good
    # Idea to read the unittest documentation. [1] What you need to know is
    # that, when a test runner executes a `TestCase` class:
    #
    # 1. `setUpClass` runs once.
    # 2. The `test*` methods run in alphabetic order. `setUp` and `tearDown`
    #    run before and after every `test*` method.
    # 3. `tearDownClass` runs once.
    #
    # The `BaseAPITestCase` adds only a little bit to this formula:
    #
    # 1. When `setUpClass` runs, a `ServerConfig` object and an empty set are
    #    instantiated. They are saved as class variables named `cfg` and
    #    `resources`, respectively.
    # 2. When `tearDownClass` runs, an HTTP DELETE call is made for each URL
    #    that has been added to `resources`. Other clean-up actions may also
    #    execute.
    #
    # This garbage collection scheme is simple. However, it's also fragile, and
    # stray resources may be left behind. For this and other reasons, Pulp
    # Smash shouldn't be run against valuable Pulp systems.
    #
    # [1] https://docs.python.org/3/library/unittest.html

    @classmethod
    def setUpClass(cls):
        """Successfully log in to the server."""
        # The `cls` object tells the new `Client` object where the Pulp server
        # is, what the authentication credentials are, and so on.
        #
        # There are several assertions that can be made about the login API
        # call. Rather than logging in logging in once for every test, we log
        # in just once, and make multiple assertions about that log in.
        super(LoginSuccessTestCase, cls).setUpClass()
        cls.response = api.Client(cls.cfg).post(LOGIN_PATH)

    def test_status_code(self):
        """Assert that the response has an HTTP 200 status code."""
        self.assertEqual(self.response.status_code, 200)

    def test_body(self):
        """Assert that the response is valid JSON and has correct keys."""
        self.assertEqual(frozenset(self.response.json().keys()), LOGIN_KEYS)


class LoginFailureTestCase(utils.BaseAPITestCase):
    """Tests for unsuccessfully logging in."""

    @classmethod
    def setUpClass(cls):
        """Unsuccessfully log in to the server."""
        # `Client` objects munge every response they receive. By default, it
        # acts safely, and does things like raising an exception if the
        # response has an HTTP 4XX or 5XX status code. We don't want that to
        # happen in this test case. So, we pass the `Client` object a different
        # function with which to munge responses. In addition, we override the
        # default authentication handling for just this one API call.
        #
        # The API and CLI clients are interesting and capable classes. Read
        # about them.
        super(LoginFailureTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.echo_handler)
        cls.response = client.post(LOGIN_PATH, auth=('', ''))

    def test_status_code(self):
        """Assert that the response has an HTTP 401 status code."""
        self.assertEqual(self.response.status_code, 401)

    def test_body(self):
        """Assert that the response is valid JSON and has correct keys."""
        # The `version` attribute should correspond to the version of the Pulp
        # server under test. This block of code says "if bug 1412 is not fixed
        # in Pulp version X, then skip this test."
        if selectors.bug_is_untestable(1412, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1412')
        self.assertEqual(frozenset(self.response.json().keys()), ERROR_KEYS)
