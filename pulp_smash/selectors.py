# coding=utf-8
"""Tools for selecting and deselecting tests."""
from __future__ import unicode_literals

import warnings
from functools import wraps

import requests
from packaging.version import Version

from pulp_smash import exceptions

# These are all possible values for a bug's "status" field.
#
# These statuses apply to bugs filed at https://pulp.plan.io. They are ordered
# according to an ideal workflow. As of this writing, these is no canonical
# public source for this information. But see:
# http://pulp.readthedocs.org/en/latest/dev-guide/contributing/bugs.html#fixing
_UNTESTABLE_BUGS = frozenset((
    'NEW',  # bug just entered into tracker
    'ASSIGNED',  # bug has been assigned to an engineer
    'POST',  # bug fix is being reviewed by dev ("posted for review")
))
_TESTABLE_BUGS = frozenset((
    'MODIFIED',  # bug fix has been accepted by dev
    'ON_QA',  # bug fix is being reviewed by qe
    'VERIFIED',  # bug fix has been accepted by qe
    'CLOSED - CURRENTRELEASE',
    'CLOSED - DUPLICATE',
    'CLOSED - NOTABUG',
    'CLOSED - WONTFIX',
    'CLOSED - WORKSFORME',
))

# A mapping between bug IDs and bug statuses. Used by `_get_bug_status`.
#
# Bug IDs and statuses should be integers and strings, respectively. Example:
#
#     _BUG_STATUS_CACHE[1356] → 'NEW'
#     _BUG_STATUS_CACHE['1356'] → KeyError
#
_BUG_STATUS_CACHE = {}


def _get_bug_status(bug_id):
    """Fetch information about bug ``bug_id`` from https://pulp.plan.io."""
    # Declaring as global right before assignment triggers: `SyntaxWarning:
    # name '_BUG_STATUS_CACHE' is used prior to global declaration`
    global _BUG_STATUS_CACHE  # pylint:disable=global-variable-not-assigned

    # It's rarely a good idea to do type checking in a duck-typed language.
    # However, efficiency dictates we do so here. Without this type check, the
    # following will cause us to talk to the bug tracker twice and store two
    # values in the cache:
    #
    #     _get_bug_status(1356)
    #     _get_bug_status('1356')
    #
    if not isinstance(bug_id, int):
        raise TypeError(
            'Bug IDs should be integers. The given ID, {} is a {}.'
            .format(bug_id, type(bug_id))
        )
    try:
        return _BUG_STATUS_CACHE[bug_id]
    except KeyError:
        pass

    # Get, cache and return bug status.
    response = requests.get(
        'https://pulp.plan.io/issues/{}.json'.format(bug_id)
    )
    response.raise_for_status()
    _BUG_STATUS_CACHE[bug_id] = response.json()['issue']['status']['name']
    return _BUG_STATUS_CACHE[bug_id]


def bug_is_testable(bug_id):
    """Tell the caller whether bug ``bug_id`` should be tested.

    :param bug_id: An integer bug ID, taken from https://pulp.plan.io.
    :returns: ``True`` if the bug is testable, or ``False`` otherwise.
    :raises: ``TypeError`` if ``bug_id`` is not an integer.
    :raises pulp_smash.exceptions.BugStatusUnknownError: If the bug has a
        status Pulp Smash does not recognize.
    :raises: BugTrackerUnavailableWarning: If the bug tracker cannot be
        contacted.
    """
    try:
        status = _get_bug_status(bug_id)
    except requests.exceptions.ConnectionError as err:
        message = (
            'Cannot contact the bug tracker. Pulp Smash will assume that the '
            'bug referenced is testable. Error: {}'.format(err)
        )
        warnings.warn(message, RuntimeWarning)
        return True

    if status in _TESTABLE_BUGS:
        return True
    elif status in _UNTESTABLE_BUGS:
        return False
    else:
        # Alternately, we could raise a warning and `return True`.
        raise exceptions.BugStatusUnknownError(
            'Bug {} has a status of {}. Pulp Smash only knows how to handle '
            'the following statuses: {}'
            .format(bug_id, status, _TESTABLE_BUGS | _UNTESTABLE_BUGS)
        )


def bug_is_untestable(bug_id):
    """Return the inverse of :meth:`bug_is_testable`."""
    return not bug_is_testable(bug_id)


def require(version_string):
    """A decorator for optionally skipping test methods.

    This decorator concisely encapsulates a common pattern for skipping tests.
    It can be used like so:

    >>> from pulp_smash.config import get_config
    >>> from pulp_smash.utils import require
    >>> from unittest import TestCase
    >>> class MyTestCase(TestCase):
    ...
    ...     @classmethod
    ...     def setUpClass(cls):
    ...         cls.cfg = get_config()
    ...
    ...     @require('2.7')  # References `self.cfg`
    ...     def test_foo(self):
    ...         pass  # Add a test for Pulp 2.7+ here.

    Notice that ``cls.cfg`` is assigned to. This is a **requirement**.

    :param version_string: A PEP 440 compatible version string.
    """
    # Running the test suite can take a long time. Let's parse the version
    # string now instead of waiting until the test is running.
    min_version = Version(version_string)

    def plain_decorator(test_method):
        """An argument-less decorator. Accepts the function being wrapped."""
        @wraps(test_method)
        def new_test_method(self, *args, **kwargs):
            """A wrapper around a test method."""
            if self.cfg.version < min_version:
                self.skipTest(
                    'This test requires Pulp {} or later, but Pulp {} is '
                    'being tested. If this seems wrong, try checking the '
                    '"settings" option in the Pulp Smash configuration file.'
                    .format(version_string, self.cfg.version)
                )
            return test_method(self, *args, **kwargs)
        return new_test_method
    return plain_decorator
