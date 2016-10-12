# coding=utf-8
"""Values usable by multiple test modules."""
from urllib.parse import quote_plus, urljoin

PULP_FIXTURES_BASE_URL = 'https://repos.fedorapeople.org/pulp/pulp/fixtures/'
"""A URL at which generated `pulp fixtures`_ are hosted.

.. _pulp fixtures: https://github.com/PulpQE/pulp-fixtures/
"""

PULP_FIXTURES_KEY_ID = '269d9d98'
"""The 32-bit ID of the public key used to sign various fixture files.

To calculate a new key ID, find the public key used by Pulp Fixtures (it should
be in the Pulp Fixtures source code repository) and use GnuPG to examine it::

    $ gpg "$public_key_file"
    pub   rsa2048 2016-08-05 [SC]
          6EDF301256480B9B801EBA3D05A5E6DA269D9D98
    uid           Pulp QE
    sub   rsa2048 2016-08-05 [E]

The last 32 bits (8 characters) of the key ID are what Pulp wants — in this
example, 269D9D98.
"""

CALL_REPORT_KEYS = frozenset(('error', 'result', 'spawned_tasks'))
"""See: `Call Report`_.

.. _Call Report:
    http://docs.pulpproject.org/en/latest/dev-guide/conventions/sync-v-async.html#call-report
"""

CONTENT_SOURCES_PATH = '/etc/pulp/content/sources/conf.d'
"""See: `Content Sources`_.

.. _Content Sources:
    http://pulp.readthedocs.io/en/latest/user-guide/content-sources.html
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

DOCKER_IMAGE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'docker/busybox:latest.tar')
"""The URL to a Docker image as created by ``docker save``."""

DOCKER_UPSTREAM_NAME = 'library/busybox'
"""The name of a repository present in each of the two docker feeds."""

DOCKER_V1_FEED_URL = 'https://index.docker.io'
"""The URL to a V1 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DOCKER_V2_FEED_URL = 'https://registry-1.docker.io'
"""The URL to a V2 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DRPM = 'drpms/test-alpha-1.1-1_1.1-2.noarch.drpm'
"""The path to a DRPM file in one of the DRPM repositories.

This path may be joined with :data:`DRPM_FEED_URL` or
:data:`DRPM_UNSIGNED_FEED_URL`.
"""

DRPM_FEED_COUNT = 4
"""The number of packages available at :data:`DRPM_FEED_URL`."""

DRPM_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm/')
"""The URL to a DRPM repository."""

DRPM_URL = urljoin(DRPM_FEED_URL, DRPM)
"""The URL to a DRPM file.

Built from :data:`DRPM_FEED_URL` and :data:`DRPM`.
"""

DRPM_UNSIGNED_FEED_COUNT = 4
"""The number of packages available at :data:`DRPM_UNSIGNED_FEED_URL`."""

DRPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm-unsigned/')
"""The URL to an unsigned DRPM repository."""

DRPM_UNSIGNED_URL = urljoin(DRPM_UNSIGNED_FEED_URL, DRPM)
"""The URL to a unsigned DRPM file.

Built from :data:`DRPM_UNSIGNED_FEED_URL` and :data:`DRPM`.
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

OSTREE_FEED = (
    'https://repos.fedorapeople.org/pulp/pulp/demo_repos/test-ostree-small'
)
"""The URL to a URL of OSTree branches. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/importer.html
"""

OSTREE_BRANCH = 'fedora-atomic/f21/x86_64/updates/docker-host'
"""A branch in :data:`OSTREE_FEED`. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/importer.html
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

PYTHON_PULP_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'python-pulp/')
"""The URL to a Pulp Python repository."""

PYTHON_EGG_URL = urljoin(
    PYTHON_PULP_FEED_URL,
    'packages/source/s/shelf-reader/shelf-reader-0.1.tar.gz'
)
"""The URL to a Python egg at :data:`PYTHON_PULP_FEED_URL`."""

PYTHON_PYPI_FEED_URL = 'https://pypi.python.org'
"""The URL to the PyPI Python repository.

.. NOTE:: This should be changed after `Pulp Fixtures #40`_ is fixed.

.. _Pulp Fixtures #40: https://github.com/PulpQE/pulp-fixtures/issues/40
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

REPOSITORY_PATH = '/pulp/api/v2/repositories/'
"""See: `Repository APIs`_.

.. _Repository APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/index.html
"""

REPOSITORY_GROUP_PATH = '/pulp/api/v2/repo_groups/'
"""See: `Repository Group APIs`_

.. _Repository Group APIs:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/groups/index.html
"""


CONSUMER_PATH = '/pulp/api/v2/consumers/'
"""See: `Consumer APIs`_.

.. _Consumer APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""

RPM_ERRATUM_ID = 'RHEA-2012:0058'
"""The ID of an erratum.

The package contained on this erratum is defined by
:data:`pulp_smash.constants.RPM_ERRATUM_RPM_NAME` and the erratum is present on
repository which feed is :data:`pulp_smash.constants.RPM_FEED_URL`.
"""

RPM_ERRATUM_RPM_NAME = 'gorilla'
"""The name of the RPM present on an erratum.

The erratum ID is defined by :data:`pulp_smash.constants.RPM_ERRATUM_ID`.
"""

RPM = 'bear-4.1-1.noarch.rpm'
"""The name of an RPM file. See :data:`pulp_smash.constants.RPM_URL`."""

RPM_ERRATUM_URL = (
    'https://repos.fedorapeople.org'
    '/repos/pulp/pulp/fixtures/rpm-erratum/erratum.json'
)
"""The URL to an JSON erratum file for an RPM repository."""

RPM_FEED_COUNT = 32
"""The number of packages available at :data:`RPM_FEED_URL`."""

RPM_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm/')
"""The URL to an RPM repository. See :data:`RPM_URL`."""

RPM_UNSIGNED_FEED_COUNT = 32
"""The number of packages available at :data:`RPM_UNSIGNED_FEED_URL`."""

RPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-unsigned/')
"""The URL to an unsigned RPM repository. See :data:`RPM_URL`."""

RPM_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FEED_URL, RPM)
"""The URL to an unsigned RPM file.

Built from :data:`RPM_UNSIGNED_FEED_URL` and :data:`RPM`.
"""

RPM_URL = urljoin(RPM_FEED_URL, RPM)
"""The URL to an RPM file. Built from :data:`RPM_FEED_URL` and :data:`RPM`."""

RPM_NAMESPACES = {
    'metadata/common': 'http://linux.duke.edu/metadata/common',
    'metadata/repo': 'http://linux.duke.edu/metadata/repo',
    'metadata/rpm': 'http://linux.duke.edu/metadata/rpm',
}
"""Namespaces used by XML-based RPM metadata.

Many of the XML files generated by the ``createrepo`` utility make use of these
namespaces. Some of the files that use these namespaces are listed below:

metadata/common
    Used by ``repodata/primary.xml``.

metadata/repo
    Used by ``repodata/repomd.xml``.

metadata/rpm
    Used by ``repodata/repomd.xml``.
"""

RPM_MIRRORLIST_BAD = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-bad')
"""The URL to a mirrorlist file containing only invalid entries."""

RPM_MIRRORLIST_GOOD = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-good')
"""The URL to a mirrorlist file containing only valid entries."""

RPM_MIRRORLIST_MIXED = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-mixed')
"""The URL to a mirrorlist file containing invalid and valid entries."""

SRPM = 'test-srpm02-1.0-1.src.rpm'
"""The name of an SRPM file at :data:`pulp_smash.constants.SRPM_FEED_URL`."""

SRPM_FEED_COUNT = 3
"""The number of packages available at :data:`SRPM_FEED_URL`."""

SRPM_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm/')
"""The URL to an SRPM repository."""

SRPM_UNSIGNED_FEED_COUNT = 3
"""The number of packages available at :data:`SRPM_UNSIGNED_FEED_COUNT`."""

SRPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-unsigned/')
"""The URL to an unsigned SRPM repository."""

SRPM_UNSIGNED_URL = urljoin(SRPM_UNSIGNED_FEED_URL, SRPM)
"""The URL to an unsigned SRPM file.

Built from :data:`SRPM_UNSIGNED_FEED_URL` and :data:`SRPM`.
"""

SRPM_URL = urljoin(SRPM_FEED_URL, SRPM)
"""The URL to an SRPM file.

Built from :data:`SRPM_FEED_URL` and :data:`SRPM`.
"""

USER_PATH = '/pulp/api/v2/users/'
"""See: `User APIs`_.

.. _User APIs:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/user/index.html
"""
