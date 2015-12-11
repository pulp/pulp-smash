# coding=utf-8
"""Values usable by multiple test modules."""
from __future__ import unicode_literals


CALL_REPORT_KEYS = frozenset(('error', 'result', 'spawned_tasks'))
"""See: `Call Report`_.

.. _Call Report:
    http://pulp.readthedocs.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report

"""

ERROR_KEYS = frozenset((
    '_href',
    'error',
    'error_message',
    'exception',
    'http_status',
    'traceback',
))
"""See: `Exception Handling`_.

No ``href`` field should be present. See `Issue #1310`_.

.. _Exception Handling:
    https://pulp.readthedocs.org/en/latest/dev-guide/conventions/exceptions.html
.. _Issue #1310: https://pulp.plan.io/issues/1310

"""

LOGIN_KEYS = frozenset(('certificate', 'key'))
"""See: `User Certificates`_.

.. _User Certificates:
    http://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/authentication.html#user-certificates

"""

LOGIN_PATH = '/pulp/api/v2/actions/login/'
"""See: `Authentication`_.

.. _Authentication:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/authentication.html

"""

REPOSITORY_PATH = '/pulp/api/v2/repositories/'
"""See: `Repository APIs`_.

.. _Repository APIs:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/repo/index.html

"""

USER_PATH = '/pulp/api/v2/users/'
"""See: `User APIs`_.

.. _User APIs:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/user/index.html

"""
