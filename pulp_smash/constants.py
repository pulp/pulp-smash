# coding=utf-8
"""Values usable by multiple test modules."""
from urllib.parse import quote_plus, urljoin
from types import MappingProxyType  # used to form an immutable dictionary

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

DOCKER_IMAGE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'docker/busybox:latest.tar')
"""The URL to a Docker image as created by ``docker save``."""

DOCKER_UPSTREAM_NAME_NOLIST = 'library/busybox'
"""The name of a Docker repository without a manifest list.

:data:`DOCKER_UPSTREAM_NAME` should be used when possible. However, this
constant is useful for backward compatibility. If Pulp is asked to sync a
repository, and:

* Pulp older than 2.14 is under test.
* The repository is configured to sync schema v2 content.
* The upstream repository has a manifest list.

…then Pulp will break when syncing. See `Pulp #2384
<https://pulp.plan.io/issues/2384>`_.
"""

DOCKER_UPSTREAM_NAME = 'dmage/manifest-list-test'
"""The name of a Docker repository.

This repository has several desireable properties:

* It is available via both :data:`DOCKER_V1_FEED_URL` and
  :data:`DOCKER_V2_FEED_URL`.
* It has a manifest list, where one entry has an architecture of amd64 and an
  os of linux. (The "latest" tag offers this.)
* It is relatively small.

This repository also has several shortcomings:

* This repository isn't an official repository. It's less trustworthy, and may
  be more likely to change with little or no notice.
* It doesn't have a manifest list where no list entries have an architecture of
  amd64 and an os of linux. (The "arm32v7" tag provides schema v1 content.)

One can get a high-level view of the content in this repository by executing:

.. code-block:: sh

    curl --location --silent \
    https://registry.hub.docker.com/v2/repositories/$this_constant/tags \
    | python -m json.tool
"""

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

This path may be joined with :data:`DRPM_SIGNED_FEED_URL` or
:data:`DRPM_UNSIGNED_FEED_URL`.
"""

DRPM_SIGNED_FEED_COUNT = 4
"""The number of packages available at :data:`DRPM_SIGNED_FEED_URL`."""

DRPM_SIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm-signed/')
"""The URL to a signed DRPM repository."""

DRPM_SIGNED_URL = urljoin(DRPM_SIGNED_FEED_URL, DRPM)
"""The URL to a DRPM file.

Built from :data:`DRPM_SIGNED_FEED_URL` and :data:`DRPM`.
"""

DRPM_UNSIGNED_FEED_COUNT = 4
"""The number of packages available at :data:`DRPM_UNSIGNED_FEED_URL`."""

DRPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm-unsigned/')
"""The URL to an unsigned DRPM repository."""

DRPM_UNSIGNED_URL = urljoin(DRPM_UNSIGNED_FEED_URL, DRPM)
"""The URL to a unsigned DRPM file.

Built from :data:`DRPM_UNSIGNED_FEED_URL` and :data:`DRPM`.
"""

FILE_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file/')
"""The URL to a file repository."""

FILE_FEED_COUNT = 3
"""The number of packages available at :data:`FILE_FEED_URL`."""

FILE_MIXED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file-mixed/')
"""The URL to a file repository containing invalid and valid entries."""

FILE_URL = urljoin(FILE_FEED_URL, '1.iso')
"""The URL to an ISO file at :data:`FILE_FEED_URL`."""

FILE2_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file2/')
"""The URL to a file repository."""

FILE2_URL = urljoin(FILE2_FEED_URL, '1.iso')
"""The URL to an ISO file at :data:`FILE2_FEED_URL`."""

OSTREE_BRANCHES = ['rawhide', 'stable']
"""A branch in :data:`OSTREE_FEED`. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/importer.html
"""

OSTREE_FEED = urljoin(PULP_FIXTURES_BASE_URL, 'ostree/small/')
"""The URL to a URL of OSTree branches. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/importer.html
"""

PUPPET_MODULE_1 = {
    'author': 'pulpqe',
    'name': 'dummypuppet',
    'version': '0.1.0'
}
"""Information about a Puppet module available via Pulp Fixtures."""

PUPPET_MODULE_URL_1 = urljoin(
    urljoin(PULP_FIXTURES_BASE_URL, 'puppet/'),
    '{}-{}.tar.gz'.format(PUPPET_MODULE_1['author'], PUPPET_MODULE_1['name'])
)
"""The URL to a Puppet module module available via Pulp Fixtures.

Test cases that require a single module should use this URL, and test cases
that require a feed should use :data:`PUPPET_MODULE_URL_2`. Doing so shifts
load away from the Puppet Forge.

Why do both URLs exist? Because simulating the Puppet Forge's behaviour is
unreasonably hard.

Pulp Fixtures is designed to create data that can be hosted by a simple HTTP
server, such as ``python3 -m http.server``. A dynamic API, such as the `Puppet
Forge API`_, cannot be simulated. We could create a static tree of files, where
that tree of files is the same as what the Puppet Forge would provide in
response to a certain HTTP GET request. However:

* The `Puppet Forge API`_ will inevitably change over time as bugs are fixed
  and features are added. This will make a static facsimile of the Puppet Forge
  API outdated. This is more than a mere inconvenience: outdated information is
  also confusing!
* Without an in-depth understanding of each and every file the Puppet Forge
  yields, it is probable that static fixtures will be wrong from the get-go.

.. _Puppet Forge API: https://forgeapi.puppetlabs.com/
"""

PUPPET_FEED_2 = 'http://forge.puppetlabs.com'
"""The URL to a repository of Puppet modules."""

PUPPET_MODULE_2 = {'author': 'pulp', 'name': 'pulp', 'version': '1.0.0'}
"""Information about a Puppet module available at :data:`PUPPET_FEED_2`."""

PUPPET_MODULE_URL_2 = ('{}/v3/files/{}-{}-{}.tar.gz'.format(
    PUPPET_FEED_2,
    PUPPET_MODULE_2['author'],
    PUPPET_MODULE_2['name'],
    PUPPET_MODULE_2['version'],
))
"""The URL to a Puppet module available at :data:`PUPPET_FEED_2`."""

PUPPET_QUERY_2 = quote_plus('-'.join(
    PUPPET_MODULE_2[key] for key in ('author', 'name', 'version')
))
"""A query that can be used to search for Puppet modules.

Built from :data:`PUPPET_MODULE_2`.

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

.. _Puppet Forge API: https://forgeapi.puppetlabs.com/
"""

PYTHON_PYPI_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'python-pypi/')
"""The URL to the PyPI Python repository."""

PYTHON_EGG_URL = urljoin(
    PYTHON_PYPI_FEED_URL,
    'packages/3a/e3/a6954c4134a899c0006515fbd40208922572947e960b35d0d19fd5a1b3'
    'd0/shelf-reader-0.1.tar.gz'
)
"""The URL to a Python egg at :data:`PYTHON_PYPI_FEED_URL`."""

PYTHON_WHEEL_URL = urljoin(
    PYTHON_PYPI_FEED_URL,
    'packages/77/e0/2156a3da94ee16466a5936394caf7e89873a9b46eed72a9912bc90e42d'
    'bf/shelf_reader-0.1-py2-none-any.whl'
)
"""The URL to a Python egg at :data:`PYTHON_PYPI_FEED_URL`."""

RPM_DATA = MappingProxyType({
    'name': 'bear',
    'epoch': '0',
    'version': '4.1',
    'release': '1',
    'arch': 'noarch',
    'metadata': {
        'release': '1',
        'license': 'GPLv2',
        'description': 'A dummy package of bear',
        'files': {'dir': [], 'file': ['/tmp/bear.txt']},
        'group': 'Internet/Applications',
        'size': {'installed': 42, 'package': 1846},
        'sourcerpm': 'bear-4.1-1.src.rpm',
        'summary': 'A dummy package of bear',
        'vendor': None,
    },
})
"""Metadata for an RPM with an associated erratum.

The metadata tags that may be present in an RPM may be printed with:

.. code-block:: sh

    rpm --querytags

Metadata for an RPM can be printed with a command like the following:

.. code-block:: sh

    for tag in name epoch version release arch vendor; do
        echo "$(rpm -qp bear-4.1-1.noarch.rpm --qf "%{$tag}")"
    done

There are three ways to measure the size of an RPM:

installed size
    The size of all the regular files in the payload.
archive size
    The uncompressed size of the payload, including necessary CPIO headers.
package size
    The actual size of an RPM file, as returned by ``stat --format='%s' …``.

For more information, see the Fedora documentation on `RPM headers
<https://docs.fedoraproject.org/en-US/Fedora_Draft_Documentation/0.1/html/RPM_Guide/ch-package-structure.html#id623000>`_.
"""

RPM = '{}-{}{}-{}.{}.rpm'.format(
    RPM_DATA['name'],
    RPM_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM_DATA['version'],
    RPM_DATA['release'],
    RPM_DATA['arch'],
)
"""The name of an RPM file. See :data:`pulp_smash.constants.RPM_SIGNED_URL`."""

RPM2_DATA = MappingProxyType({
    'name': 'camel',
    'epoch': '0',
    'version': '0.1',
    'release': '1',
    'arch': 'noarch',
    'metadata': {
        'release': '1',
        'license': 'GPLv2',
        'description': 'A dummy package of camel',
        'files': {'dir': [], 'file': ['/tmp/camel.txt']},
        'group': 'Internet/Applications',
        'size': '42',
        'sourcerpm': 'camel-0.1-1.src.rpm',
        'summary': 'A dummy package of camel',
        'vendor': None,
    },
})

RPM2 = '{}-{}{}-{}.{}.rpm'.format(
    RPM2_DATA['name'],
    RPM2_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM2_DATA['version'],
    RPM2_DATA['release'],
    RPM2_DATA['arch'],
)
"""The name of an RPM. See :data:`pulp_smash.constants.RPM2_UNSIGNED_URL`."""

RPM_WITH_VENDOR_DATA = MappingProxyType({
    'name': 'rpm-with-vendor',
    'epoch': '0',
    'version': '1',
    'release': '1.fc25',
    'arch': 'noarch',
    'metadata': {
        'release': '1',
        'license': 'Public Domain',
        'description': 'This RPM has a vendor',
        'files': {'dir': [], 'file': []},
        'group': None,
        'size': None,
        'sourcerpm': None,
        'summary': None,
        'vendor': 'Pulp Fixtures',
    },
})

RPM_WITH_VENDOR = '{}-{}{}-{}.{}.rpm'.format(
    RPM_WITH_VENDOR_DATA['name'],
    RPM_WITH_VENDOR_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM_WITH_VENDOR_DATA['version'],
    RPM_WITH_VENDOR_DATA['release'],
    RPM_WITH_VENDOR_DATA['arch'],
)
"""The name of an RPM. See :data:`pulp_smash.constants.RPM_WITH_VENDOR_URL`."""

RPM_ALT_LAYOUT_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-alt-layout/')
"""The URL to a signed RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_INCOMPLETE_FILELISTS_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-incomplete-filelists/',
)
"""The URL to a repository with an incomplete ``filelists.xml`` file."""

RPM_INCOMPLETE_OTHER_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-incomplete-other/',
)
"""The URL to a repository with an incomplete ``other.xml`` file."""

RPM_ERRATUM_ID = 'RHEA-2012:0058'
"""The ID of an erratum.

The package contained on this erratum is defined by
:data:`pulp_smash.constants.RPM_ERRATUM_RPM_NAME` and the erratum is present on
repository which feed is :data:`pulp_smash.constants.RPM_SIGNED_FEED_URL`.
"""

RPM_ERRATUM_RPM_NAME = 'gorilla'
"""The name of the RPM named by :data:`pulp_smash.constants.RPM_ERRATUM_ID`."""

RPM_ERRATUM_COUNT = 4
"""The number of errata in :data:`RPM_UNSIGNED_FEED_URL`."""

RPM_INVALID_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-invalid-rpm/')
"""The URL to an invalid RPM repository."""

RPM_INVALID_URL = urljoin(RPM_INVALID_FEED_URL, 'invalid.rpm')
"""The URL to an invalid RPM package."""

RPM_LARGE_UPDATEINFO = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-long-updateinfo/')
"""The URL to RPM with a large updateinfo.xml."""

RPM_MIRRORLIST_LARGE = (
    'https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=x86_64'
)
"""A mirrorlist referencing a large RPM repository.

.. NOTE: The mirrors referenced by this mirrorlist are not operated by Pulp QE.
    They're public resources and should be sparingly used.
"""

RPM_MIRRORLIST_BAD = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-bad')
"""The URL to a mirrorlist file containing only invalid entries."""

RPM_MIRRORLIST_GOOD = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-good')
"""The URL to a mirrorlist file containing only valid entries."""

RPM_MIRRORLIST_MIXED = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-mixed')
"""The URL to a mirrorlist file containing invalid and valid entries."""

RPM_MISSING_FILELISTS_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-missing-filelists/',
)
"""A repository that's missing its ``filelists.xml`` file."""

RPM_MISSING_OTHER_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-missing-other/',
)
"""A repository that's missing its ``other.xml`` file."""

RPM_MISSING_PRIMARY_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-missing-primary/',
)
"""A repository that's missing its ``primary.xml`` file."""

RPM_NAMESPACES = {
    'metadata/common': 'http://linux.duke.edu/metadata/common',
    'metadata/filelists': 'http://linux.duke.edu/metadata/filelists',
    'metadata/other': 'http://linux.duke.edu/metadata/other',
    'metadata/repo': 'http://linux.duke.edu/metadata/repo',
    'metadata/rpm': 'http://linux.duke.edu/metadata/rpm',
}
"""Namespaces used by XML-based RPM metadata.

Many of the XML files generated by the ``createrepo`` utility make use of these
namespaces. Some of the files that use these namespaces are listed below:

metadata/common
    Used by ``repodata/primary.xml``.

metadata/filelists
    Used by ``repodata/filelists.xml``.

metadata/other
    Used by ``repodata/other.xml``.

metadata/repo
    Used by ``repodata/repomd.xml``.

metadata/rpm
    Used by ``repodata/repomd.xml``.
"""

RPM_PKGLISTS_UPDATEINFO_FEED_URL = (
    'https://repos.fedorapeople.org/pulp/pulp/fixtures/'
    'rpm-pkglists-updateinfo/'
)
"""A repository whose updateinfo file has multiple ``<pkglist>`` sections."""

RPM_SIGNED_FEED_COUNT = 32
"""The number of packages available at :data:`RPM_SIGNED_FEED_URL`."""

RPM_SIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-signed/')
"""The URL to a signed RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_SIGNED_URL = urljoin(RPM_SIGNED_FEED_URL, RPM)
"""The URL to an RPM file.

Built from :data:`RPM_SIGNED_FEED_URL` and :data:`RPM`.
"""

RPM_UNSIGNED_FEED_COUNT = 32
"""The number of packages available at :data:`RPM_UNSIGNED_FEED_URL`."""

RPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-unsigned/')
"""The URL to an unsigned RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FEED_URL, RPM)
"""The URL to an unsigned RPM file.

Built from :data:`RPM_UNSIGNED_FEED_URL` and :data:`RPM`.
"""

RPM_UPDATED_INFO_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-updated-updateinfo/'
)
"""A repository whose updateinfo file has an errata section."""

RPM2_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FEED_URL, RPM2)
"""The URL to an unsigned RPM file.

Built from :data:`RPM_UNSIGNED_FEED_URL` and :data:`RPM2`.
"""

RPM_WITH_PULP_DISTRIBUTION_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-with-pulp-distribution/')
"""The URL to a RPM repository with a PULP_DISTRIBUTION.xml file."""

RPM_WITH_NON_ASCII_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-non-ascii/rpm-with-non-ascii-1-1.fc25.noarch.rpm'
)
"""The URL to an RPM with non-ascii metadata in its header."""

RPM_WITH_NON_UTF_8_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-non-utf-8/rpm-with-non-utf-8-1-1.fc25.noarch.rpm'
)
"""The URL to an RPM with non-UTF-8 metadata in its header."""

RPM_WITH_VENDOR_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-vendor/'
)
"""A repository whose primary.xml file has an vendor section."""

RPM_WITH_VENDOR_URL = urljoin(
    RPM_WITH_VENDOR_FEED_URL,
    'rpm-with-vendor-1-1.fc25.noarch.rpm'
)
"""The URL of an RPM with a specified vendor in its header."""

SRPM = 'test-srpm02-1.0-1.src.rpm'
"""An SRPM file at :data:`pulp_smash.constants.SRPM_SIGNED_FEED_URL`."""

SRPM_SIGNED_FEED_COUNT = 3
"""The number of packages available at :data:`SRPM_SIGNED_FEED_URL`."""

SRPM_SIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-signed/')
"""The URL to a signed SRPM repository."""

SRPM_SIGNED_URL = urljoin(SRPM_SIGNED_FEED_URL, SRPM)
"""The URL to an SRPM file.

Built from :data:`SRPM_SIGNED_FEED_URL` and :data:`SRPM`.
"""

SRPM_UNSIGNED_FEED_COUNT = 3
"""The number of packages available at :data:`SRPM_UNSIGNED_FEED_COUNT`."""

SRPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-unsigned/')
"""The URL to an unsigned SRPM repository."""

SRPM_UNSIGNED_URL = urljoin(SRPM_UNSIGNED_FEED_URL, SRPM)
"""The URL to an unsigned SRPM file.

Built from :data:`SRPM_UNSIGNED_FEED_URL` and :data:`SRPM`.
"""
