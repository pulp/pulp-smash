# coding=utf-8
"""Values usable by multiple test modules."""
from __future__ import unicode_literals

from pulp_smash.compat import quote_plus, urljoin


CALL_REPORT_KEYS = frozenset(('error', 'result', 'spawned_tasks'))
"""See: `Call Report`_.

.. _Call Report:
    http://pulp.readthedocs.io/en/latest/dev-guide/conventions/sync-v-async.html#call-report
"""

CONTENT_UPLOAD_PATH = '/pulp/api/v2/content/uploads/'
"""See: `Creating an Upload Request`_.

.. _Creating an Upload Request:
   http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/upload.html#creating-an-upload-request
"""

DOCKER_IMAGE_URL = (
    'https://repos.fedorapeople.org/repos/pulp/pulp/fixtures/docker/'
    'busybox:latest.tar'
)
"""The URL to a Docker image as created by ``docker save``."""

DOCKER_V1_FEED_URL = 'https://index.docker.io'
"""The URL to a V1 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DOCKER_V2_FEED_URL = 'https://registry-1.docker.io'
"""The URL to a V2 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DRPM_FEED_URL = (
    'https://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/test_drpm_repo/'
)
"""The URL to an DRPM repository."""

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
    https://pulp.readthedocs.io/en/latest/dev-guide/conventions/exceptions.html
.. _Issue #1310: https://pulp.plan.io/issues/1310
"""

GROUP_CALL_REPORT_KEYS = frozenset(('_href', 'group_id'))
"""See: `Group Call Report`_.

.. _Group Call Report:
    http://pulp.readthedocs.io/en/latest/dev-guide/conventions/sync-v-async.html#group-call-report
"""

LOGIN_KEYS = frozenset(('certificate', 'key'))
"""See: `User Certificates`_.

.. _User Certificates:
    http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/authentication.html#user-certificates
"""

LOGIN_PATH = '/pulp/api/v2/actions/login/'
"""See: `Authentication`_.

.. _Authentication:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/authentication.html
"""

ORPHANS_PATH = 'pulp/api/v2/content/orphans/'
"""See: `Orphaned Content`_.

.. _Orphaned Content:
    http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/orphan.html
"""

OSTREE_FEED = (
    'https://repos.fedorapeople.org/pulp/pulp/demo_repos/test-ostree-small'
)
"""The URL to a URL of OSTree branches. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://pulp-ostree.readthedocs.io/en/latest/tech-reference/importer.html
"""

OSTREE_BRANCH = 'fedora-atomic/f21/x86_64/updates/docker-host'
"""A branch in :data:`OSTREE_FEED`. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://pulp-ostree.readthedocs.io/en/latest/tech-reference/importer.html
"""

PLUGIN_TYPES_PATH = '/pulp/api/v2/plugins/types/'
"""See: `Retrieve All Content Unit Types`_.

.. _Retrieve All Content Unit Types:
   http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/server_plugins.html#retrieve-all-content-unit-types
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

PUPPET_FEED = 'http://forge.puppetlabs.com'
"""The URL to a repository of Puppet modules."""

PUPPET_MODULE = {'author': 'pulp', 'name': 'pulp', 'version': '1.0.0'}
"""Information about a Puppet module available at :data:`PUPPET_FEED`."""

PUPPET_MODULE_URL = ('{}/v3/files/{}-{}-{}.tar.gz'.format(
    PUPPET_FEED,
    PUPPET_MODULE['author'],
    PUPPET_MODULE['name'],
    PUPPET_MODULE['version'],
))
"""The URL to a Puppet module available at :data:`PUPPET_FEED`."""

PUPPET_QUERY = quote_plus('-'.join(
    PUPPET_MODULE[key] for key in ('author', 'name', 'version')
))
"""A query that can be used to search for Puppet modules.

Built from :data:`PUPPET_MODULE`.

Though the `Puppet Forge API`_ supports a variety of search types, Pulp
only supports the ability to search for modules. As a result, it is
impossible to create a Puppet repository and sync only an exact module or
set of modules. This query intentionally returns a small number of Puppet
modules. A query which selected a large number of modules would produce
tests that took a long time and abused the free Puppet Forge service.

Beware that the Pulp API takes given Puppet queries and uses them to construct
URL queries verbatim. Thus, if the user gives a query of "foo bar", the
following URL is constructed:

    https://forge.puppet.com/modules.json/q=foo bar

In an attempt to avoid this error, this query is encoded before being submitted
to Pulp.

.. _Puppet Forge API:
    http://projects.puppetlabs.com/projects/module-site/wiki/Server-api
"""

PYTHON_EGG_URL = (
    'https://pypi.python.org/packages/source/p/pulp-smash/'
    'pulp-smash-2016.4.14.tar.gz'
)
"""The URL to a Python egg."""

PYTHON_WHEEL_URL = (
    'https://pypi.python.org/packages/py2.py3/p/pulp-smash/'
    'pulp_smash-2016.4.14-py2.py3-none-any.whl'
)
"""The URL to a Python wheel."""

REPOSITORY_PATH = '/pulp/api/v2/repositories/'
"""See: `Repository APIs`_.

.. _Repository APIs:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/index.html
"""

CONSUMER_PATH = '/pulp/api/v2/consumers/'
"""See: `Consumer APIs`_.

.. _Consumer APIs:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""

RPM = 'bear-4.1-1.noarch.rpm'
"""The name of an RPM file. See :data:`pulp_smash.constants.RPM_URL`."""

RPM_ABS_PATH = (
    '/var/lib/pulp/content/units/rpm/76/78177c241777af22235092f21c3932d'
    'd4f0664e1624e5a2c77a201ec70f930/' + RPM
)
"""The absolute path to :data:`pulp_smash.constants.RPM` in the filesystem."""

RPM_FEED_URL = 'https://repos.fedorapeople.org/repos/pulp/pulp/fixtures/rpm/'
"""The URL to an RPM repository. See :data:`RPM_URL`."""

RPM_SHA256_CHECKSUM = (
    '7a831f9f90bf4d21027572cb503d20b702de8e8785b02c0397445c2e481d81b3'
)
"""The sha256 checksum of :data:`pulp_smash.constants.RPM`."""

RPM_URL = urljoin(RPM_FEED_URL, RPM)
"""The URL to an RPM file. Built from :data:`RPM_FEED_URL` and :data:`RPM`."""

SRPM_FEED_URL = (
    'https://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/test_srpm_repo/'
)
"""The URL to an SRPM repository."""

USER_PATH = '/pulp/api/v2/users/'
"""See: `User APIs`_.

.. _User APIs:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/user/index.html
"""
