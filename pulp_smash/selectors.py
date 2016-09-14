# coding=utf-8
"""Tools for selecting and deselecting tests."""
import warnings
from collections import namedtuple
from functools import wraps

import requests
from packaging.version import Version

from pulp_smash import exceptions

# These are all possible values for a bug's "status" field.
#
# These statuses apply to bugs filed at https://pulp.plan.io. They are ordered
# according to an ideal workflow. As of this writing, these is no canonical
# public source for this information. But see:
# http://docs.pulpproject.org/en/latest/dev-guide/contributing/bugs.html#fixing
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

# A mapping between bug IDs and bug statuses. Used by `_get_bug`.
#
# Bug IDs and statuses should be integers and strings, respectively. Example:
#
#     _BUG_STATUS_CACHE[1356] → _Bug(status='NEW', target_platform_release=…)
#     _BUG_STATUS_CACHE['1356'] → KeyError
#
_BUG_STATUS_CACHE = {}


# Information about a Pulp bug. (See: https://pulp.plan.io)
#
# The 'status' attribute is a string, such as 'NEW' or 'ASSIGNED'. The
# 'target_platform_release' attribute is a Version() object.
_Bug = namedtuple('_Bug', ('status', 'target_platform_release'))


def _get_tpr(bug_json):
    """Return a bug's Target Platform Release (TPR) field.

    :param bug_json: A JSON representation of a Pulp bug. (For example, see:
        https://pulp.plan.io/issues/1.json)
    :returns: A ``packaging.version.Version`` object.
    :raises pulp_smash.exceptions.BugTPRMissingError: If no "Target Platform
        Release" field is found in ``bug_json``.
    """
    custom_field_id = 4
    custom_fields = bug_json['issue']['custom_fields']
    for custom_field in custom_fields:
        if custom_field['id'] == custom_field_id:
            return custom_field['value']
    raise exceptions.BugTPRMissingError(
        'Bug {} has no custom field with ID {} ("Target Platform Release"). '
        'Custom fields: {}'
        .format(bug_json['issue']['id'], custom_field_id, custom_fields)
    )


def _convert_tpr(version_string):
    """Convert a Target Platform Release (TPR) string to a ``Version`` object.

    By default, a bug's TPR string is an empty string. It is unlikely to be set
    until a fix has been implemented, and even then, it is quite possible that
    the field will be left as an empty string. (Perhaps the user forgot to set
    it, or set it to the wrong value.)

    If ``version_string == ''``, this method pretends that ``version_string ==
    '0'``. Why is this useful? Let's imagine that a bug has a status of
    MODIFIED and a TPR of "": we can now assume that this bug is fixed in all
    versions of Pulp. More generally, any time a bug is marked as fixed and no
    TPR listed, we assume that the bug is fixed for all versions of Pulp.

    :param version_string: A version string like "2.8.1" or "".
    :returns: A ``packaging.version.Version`` object.
    :raises: ``packaging.version.InvalidVersion`` if ``version_string`` is
        invalid and not "".
    """
    if version_string == '':
        return Version('0')
    return Version(version_string)


def _get_bug(bug_id):
    """Fetch information about bug ``bug_id`` from https://pulp.plan.io.

    Return a ``_Bug`` instance.
    """
    # It's rarely a good idea to do type checking in a duck-typed language.
    # However, efficiency dictates we do so here. Without this type check, the
    # following will cause us to talk to the bug tracker twice and store two
    # values in the cache:
    #
    #     _get_bug(1356)
    #     _get_bug('1356')
    #
    if not isinstance(bug_id, int):
        raise TypeError(
            'Bug IDs should be integers. The given ID, {} is a {}.'
            .format(bug_id, type(bug_id))
        )

    # Let's return the bug from the cache if possible. ¶ We shouldn't need to
    # declare a global until we want to assign to it, but waiting causes Python
    # itself to emit a SyntaxWarning.
    global _BUG_STATUS_CACHE  # pylint:disable=global-variable-not-assigned
    try:
        return _BUG_STATUS_CACHE[bug_id]
    except KeyError:
        pass

    # The bug is not cached. Let's fetch, cache and return it.
    response = requests.get(
        'https://pulp.plan.io/issues/{}.json'.format(bug_id)
    )
    response.raise_for_status()
    bug_json = response.json()
    _BUG_STATUS_CACHE[bug_id] = _Bug(
        bug_json['issue']['status']['name'],
        _convert_tpr(_get_tpr(bug_json)),
    )
    return _BUG_STATUS_CACHE[bug_id]


def bug_is_testable(bug_id, pulp_version):
    """Tell the caller whether bug ``bug_id`` should be tested.

    :param bug_id: An integer bug ID, taken from https://pulp.plan.io.
    :param pulp_version: A ``packaging.version.Version`` object telling the
        version of the Pulp server we are testing.
    :returns: ``True`` if the bug is testable, or ``False`` otherwise.
    :raises: ``TypeError`` if ``bug_id`` is not an integer.
    :raises pulp_smash.exceptions.BugStatusUnknownError: If the bug has a
        status Pulp Smash does not recognize.
    """
    try:
        bug = _get_bug(bug_id)
    except requests.exceptions.ConnectionError as err:
        message = (
            'Cannot contact the bug tracker. Pulp Smash will assume that the '
            'bug referenced is testable. Error: {}'.format(err)
        )
        warnings.warn(message, RuntimeWarning)
        return True

    # bug.target_platform_release has already been verified by Version().
    if bug.status not in _TESTABLE_BUGS | _UNTESTABLE_BUGS:
        raise exceptions.BugStatusUnknownError(
            'Bug {} has a status of {}. Pulp Smash only knows how to handle '
            'the following statuses: {}'
            .format(bug_id, bug.status, _TESTABLE_BUGS | _UNTESTABLE_BUGS)
        )

    # Finally, we have good data!
    if (bug.status in _TESTABLE_BUGS and
            bug.target_platform_release <= pulp_version):
        return True
    return False


def bug_is_untestable(bug_id, pulp_version):
    """Return the inverse of :meth:`bug_is_testable`."""
    return not bug_is_testable(bug_id, pulp_version)


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
