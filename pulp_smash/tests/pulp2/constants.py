# coding=utf-8
"""Constants for Pulp 2 tests."""

from urllib.parse import urljoin


CALL_REPORT_KEYS = frozenset(('error', 'result', 'spawned_tasks'))
"""See: `Call Report`_.

.. _Call Report:
    http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report
"""

CONSUMERS_PATH = '/pulp/api/v2/consumers/'
"""See: `Consumer APIs`_.

.. _Consumer APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""

CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH = urljoin(
    CONSUMERS_PATH,
    'actions/content/regenerate_applicability/',
)
"""See: `Content Applicability`_.

.. _Content Applicability:
    http://docs.pulpproject.org/dev-guide/integration/rest-api/consumer/applicability.html
"""

CONSUMERS_CONTENT_APPLICABILITY_PATH = urljoin(
    CONSUMERS_PATH,
    'content/applicability/',
)
"""See: `Content Applicability`_.

.. _Content Applicability:
    http://docs.pulpproject.org/dev-guide/integration/rest-api/consumer/applicability.html
"""

CONTENT_SOURCES_PATH = '/etc/pulp/content/sources/conf.d'
"""See: `Content Sources`_.

.. _Content Sources:
    https://docs.pulpproject.org/user-guide/content-sources.html
"""

CONTENT_UNITS_PATH = '/pulp/api/v2/content/units/'
"""See: `Search for Units`_.

.. _Search for Units:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/units.html#search-for-units
"""

CONTENT_UPLOAD_PATH = '/pulp/api/v2/content/uploads/'
"""See: `Creating an Upload Request`_.

.. _Creating an Upload Request:
   http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/upload.html#creating-an-upload-request
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
    https://docs.pulpproject.org/en/latest/dev-guide/conventions/exceptions.html
.. _Issue #1310: https://pulp.plan.io/issues/1310
"""

GROUP_CALL_REPORT_KEYS = frozenset(('_href', 'group_id'))
"""See: `Group Call Report`_.

.. _Group Call Report:
    http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html#group-call-report
"""

LOGIN_KEYS = frozenset(('certificate', 'key'))
"""See: `User Certificates`_.

.. _User Certificates:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/authentication.html#user-certificates
"""

LOGIN_PATH = '/pulp/api/v2/actions/login/'
"""See: `Authentication`_.

.. _Authentication:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/authentication.html
"""

ORPHANS_PATH = 'pulp/api/v2/content/orphans/'
"""See: `Orphaned Content`_.

.. _Orphaned Content:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/orphan.html
"""

PLUGIN_TYPES_PATH = '/pulp/api/v2/plugins/types/'
"""See: `Retrieve All Content Unit Types`_.

.. _Retrieve All Content Unit Types:
   http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/server_plugins.html#retrieve-all-content-unit-types
"""

PULP_SERVICES = {
    'httpd',
    'pulp_celerybeat',
    'pulp_resource_manager',
    'pulp_workers',
}
"""Core Pulp services.

There are services beyond just these that Pulp depends on in order to function
correctly. For example, an AMQP broker such as RabbitMQ or Qpid is integral to
Pulp's functioning. However, if resetting Pulp (such as in
:func:`pulp_smash.utils.reset_pulp`), this is the set of services that should
be restarted.
"""

REPOSITORY_EXPORT_DISTRIBUTOR = 'export_distributor'
"""A ``distributor_type_id`` to export a repository.

See: `Export Distributors
<https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/export-distributor.html>`_.
"""

REPOSITORY_GROUP_EXPORT_DISTRIBUTOR = 'group_export_distributor'
"""A ``distributor_type_id`` to export a repository group.

See: `Export Distributors
<https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/export-distributor.html>`_.
"""

REPOSITORY_GROUP_PATH = '/pulp/api/v2/repo_groups/'
"""See: `Repository Group APIs`_

.. _Repository Group APIs:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/groups/index.html
"""

REPOSITORY_PATH = '/pulp/api/v2/repositories/'
"""See: `Repository APIs`_.

.. _Repository APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/index.html
"""

TASKS_PATH = '/pulp/api/v2/tasks/'
"""See: `Tasks APIs`_.

.. _Tasks APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/tasks.html
"""

USER_PATH = '/pulp/api/v2/users/'
"""See: `User APIs`_.

.. _User APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/user/index.html
"""
