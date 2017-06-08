# coding=utf-8
"""Utility functions for Pulp tests.

This module may make use of :mod:`pulp_smash.api` and :mod:`pulp_smash.cli`,
but the reverse should not be done.
"""
import hashlib
import io
import unittest
import uuid
from urllib.parse import urljoin, urlparse

import requests
from packaging.version import Version

from pulp_smash import api, cli, config, exceptions
from pulp_smash.cli import _is_root as is_root  # for backward compatibility
from pulp_smash.constants import (
    CONTENT_UPLOAD_PATH,
    ORPHANS_PATH,
    PLUGIN_TYPES_PATH,
    PULP_SERVICES,
    REPOSITORY_PATH,
)

# A mapping between URLs and SHA 256 checksums. Used by get_sha256_checksum().
_CHECKSUM_CACHE = {}


def uuid4():
    """Return a random UUID, as a unicode string."""
    return type('')(uuid.uuid4())


# See design discussion at: https://github.com/PulpQE/pulp-smash/issues/31
def get_broker(server_config):
    """Build an object for managing the target system's AMQP broker.

    Talk to the host named by ``server_config`` and use simple heuristics to
    determine which AMQP broker is installed. If Qpid or RabbitMQ appear to be
    installed, return the name of that service. Otherwise, raise an exception.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the system on which an AMQP broker exists.
    :returns: A string such as 'qpidd' or 'rabbitmq'.
    :raises pulp_smash.exceptions.NoKnownBrokerError: If unable to find any
        AMQP brokers on the target system.
    """
    # On Fedora 23, /usr/sbin and /usr/local/sbin are only added to the $PATH
    # for login shells. (See pathmunge() in /etc/profile.) As a result, logging
    # into a system and executing `which qpidd` and remotely executing `ssh
    # pulp.example.com which qpidd` may return different results.
    client = cli.Client(server_config, cli.echo_handler)
    executables = ('qpidd', 'rabbitmq')  # ordering indicates preference
    for executable in executables:
        command = ('test', '-e', '/usr/sbin/' + executable)
        if client.run(command).returncode == 0:
            return executable
    raise exceptions.NoKnownBrokerError(
        'Unable to determine the AMQP broker used by {}. It does not appear '
        'to be any of {}.'
        .format(server_config.base_url, executables)
    )


def http_get(url, **kwargs):
    """Issue a HTTP request to the ``url`` and return the response content.

    This is useful for downloading file contents over HTTP[S].

    :param url: the URL where the content should be get.
    :param kwargs: additional kwargs to be passed to ``requests.get``.
    :returns: the response content of a GET request to ``url``.
    """
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response.content


def pulp_admin_login(server_config):
    """Execute ``pulp-admin login``.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp server being targeted.
    :return: The completed process.
    :rtype: pulp_smash.cli.CompletedProcess
    """
    cmd = 'pulp-admin login -u {} -p {}'.format(*server_config.pulp_auth)
    return cli.Client(server_config).run(cmd.split())


def reset_pulp(server_config):
    """Stop Pulp, reset its database, remove certain files, and start it.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp server being targeted.
    :returns: Nothing.
    """
    svc_mgr = cli.GlobalServiceManager(server_config)
    svc_mgr.stop(PULP_SERVICES)

    # Reset the database and nuke accumulated files.
    #
    # Why use `runuser` instead of `sudo`? Because some systems are configured
    # to refuse to execute `sudo` unless a tty is present (The author has
    # encountered this on at least one RHEL 7.2 system.)
    #
    # Why not use runuser's `-u` flag? Because RHEL 6 ships an old version of
    # runuser that doesn't support the flag, and RHEL 6 is a supported Pulp
    # platform.
    system = server_config.get_systems('mongod')[0]
    client = cli.Client(server_config, pulp_system=system)
    client.run('mongo pulp_database --eval db.dropDatabase()'.split())

    for index, system in enumerate(server_config.get_systems('api')):
        prefix = '' if is_root(server_config, pulp_system=system) else 'sudo '
        if index == 0:
            client.run((
                prefix + 'runuser --shell /bin/sh apache --command '
                'pulp-manage-db'
            ).split())
        client.run((prefix + 'rm -rf /var/lib/pulp/content').split())
        client.run((prefix + 'rm -rf /var/lib/pulp/published').split())

    svc_mgr.start(PULP_SERVICES)


def upload_import_unit(cfg, unit, import_params, repo):
    """Upload a content unit to a Pulp server and import it into a repository.

    This procedure only works for some unit types, such as ``rpm`` or
    ``python_package``. Others, like ``package_group``, require an alternate
    procedure. The procedure encapsulated by this function is as follows:

    1. Create an upload request.
    2. Upload the content unit to Pulp, in small chunks.
    3. Import the uploaded content unit into a repository.
    4. Delete the upload request.

    The default set of parameters sent to Pulp during step 3 are::

        {'unit_key': {}, 'upload_id': '…'}

    The actual parameters required by Pulp depending on the circumstances, and
    the parameters sent to Pulp may be customized via the ``import_params``
    argument. For example, if uploading a Python content unit,
    ``import_params`` should be the following::

        {'unit_key': {'filename': '…'}, 'unit_type_id': 'python_package'}

    This would result in the following upload parameters being used::

        {
            'unit_key': {'filename': '…'},
            'unit_type_id': 'python_package',
            'upload_id': '…',
        }

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :param unit: The unit to be uploaded and imported, as a binary blob.
    :param import_params: A dict of parameters to be merged into the default
        set of import parameters during step 3.
    :param repo: A dict of information about the target repository.
    :returns: The call report returned when importing the unit.
    """
    client = api.Client(cfg, api.json_handler)
    malloc = client.post(CONTENT_UPLOAD_PATH)

    # 200,000 bytes ~= 200 kB
    chunk_size = 200000
    offset = 0
    with io.BytesIO(unit) as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:  # if chunk == b'':
                break  # we've reached EOF
            path = urljoin(malloc['_href'], '{}/'.format(offset))
            client.put(path, data=chunk)
            offset += chunk_size

    path = urljoin(repo['_href'], 'actions/import_upload/')
    body = {'unit_key': {}, 'upload_id': malloc['upload_id']}
    body.update(import_params)
    call_report = client.post(path, body)
    client.delete(malloc['_href'])
    return call_report


def upload_import_erratum(server_config, erratum, repo_href):
    """Upload an erratum to a Pulp server and import it into a repository.

    For most content types, use :meth:`upload_import_unit`.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp server being targeted.
    :param erratum: A dict, with keys such as "id," "status," "issued," and
        "references."
    :param repo_href: The path to the repository into which ``erratum`` will be
        imported.
    :returns: The call report returned when importing the erratum.
    """
    client = api.Client(server_config, api.json_handler)
    malloc = client.post(CONTENT_UPLOAD_PATH)
    call_report = client.post(urljoin(repo_href, 'actions/import_upload/'), {
        'unit_key': {'id': erratum['id']},
        'unit_metadata': erratum,
        'unit_type_id': 'erratum',
        'upload_id': malloc['upload_id'],
    })
    client.delete(malloc['_href'])
    return call_report


class BaseAPITestCase(unittest.TestCase):
    """A class with behaviour that is of use in many API test cases.

    This test case provides set-up and tear-down behaviour that is common to
    many API test cases. It is not necessary to use this class as the parent of
    all API test cases, but it serves well in many cases.
    """

    @classmethod
    def setUpClass(cls):
        """Provide a server config and an iterable of resources to delete.

        The following class attributes are created this method:

        ``cfg``
            A :class:`pulp_smash.config.PulpSmashConfig` object.
        ``resources``
            A set object. If a child class creates some resources that should
            be deleted when the test is complete, the child class should add
            that resource's href to this set.
        """
        cls.cfg = config.get_config()
        cls.resources = set()

    @classmethod
    def tearDownClass(cls):
        """Delete all resources named by ``resources``."""
        client = api.Client(cls.cfg)
        for resource in cls.resources:
            client.delete(resource)
        client.delete(ORPHANS_PATH)


class BaseAPICrudTestCase(unittest.TestCase):
    """A parent class for API CRUD test cases.

    :meth:`create_body` and :meth:`update_body` should be overridden by
    concrete child classes. The bodies of these two methods are encoded to JSON
    and used as the bodies of HTTP requests for creating and updating a
    repository, respectively. Be careful to return appropriate data when
    overriding these methods: the various ``test*`` methods assume the
    repository is fairly simple.

    Relevant Pulp documentation:

    Create
        http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#create-a-repository
    Read
        http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/retrieval.html#retrieve-a-single-repository
    Update
        http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#update-a-repository
    Delete
        http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html#delete-a-repository
    """

    @classmethod
    def setUpClass(cls):
        """Create, update, read and delete a repository."""
        client = api.Client(config.get_config())
        cls.bodies = {'create': cls.create_body(), 'update': cls.update_body()}
        cls.responses = {}
        cls.responses['create'] = client.post(
            REPOSITORY_PATH,
            cls.bodies['create'],
        )
        repo_href = cls.responses['create'].json()['_href']
        cls.responses['update'] = client.put(repo_href, cls.bodies['update'])
        cls.responses['read'] = client.get(repo_href, params={'details': True})
        cls.responses['delete'] = client.delete(repo_href)

    @staticmethod
    def create_body():
        """Return a dict for creating a repository. Should be overridden.

        :raises: ``NotImplementedError`` if not implemented by a child class.
        """
        raise NotImplementedError()

    @staticmethod
    def update_body():
        """Return a dict for updating a repository. Should be overridden.

        :raises: ``NotImplementedError`` if not implemented by a child class.
        """
        raise NotImplementedError()

    def test_status_codes(self):
        """Assert each response has a correct status code."""
        for response, code in (
                ('create', 201),
                ('update', 200),
                ('read', 200),
                ('delete', 202)):
            with self.subTest((response, code)):
                self.assertEqual(self.responses[response].status_code, code)

    def test_create(self):
        """Assert the created repository has all requested attributes.

        Walk through each of the attributes returned by :meth:`create_body` and
        verify the attribute is present in the repository.

        NOTE: Any attribute whose name starts with ``importer`` or
        ``distributor`` is not verified.
        """
        received = self.responses['create'].json()
        for key, value in self.bodies['create'].items():
            if key.startswith('importer') or key.startswith('distributor'):
                continue
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_update(self):
        """Assert the repo update response has the requested changes."""
        received = self.responses['update'].json()['result']
        for key, value in self.bodies['update']['delta'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_read(self):
        """Assert the repo update response has the requested changes."""
        received = self.responses['read'].json()
        for key, value in self.bodies['update']['delta'].items():
            with self.subTest(key=key, value=value):
                self.assertEqual(received[key], value)

    def test_number_importers(self):
        """Assert the repository has one importer."""
        self.assertEqual(len(self.responses['read'].json()['importers']), 1)

    def test_importer_type_id(self):
        """Validate the repo importer's ``importer_type_id`` attribute."""
        key = 'importer_type_id'
        type_sent = self.bodies['create'][key]
        type_received = self.responses['read'].json()['importers'][0][key]
        self.assertEqual(type_sent, type_received)

    def test_importer_config(self):
        """Validate the ``config`` attribute of each importer."""
        cfg_sent = self.bodies['create']['importer_config']
        cfg_received = self.responses['read'].json()['importers'][0]['config']
        self.assertEqual(cfg_sent, cfg_received)


# It's OK for this method to have just one method. It's a mixin.
class DuplicateUploadsMixin(object):  # pylint:disable=too-few-public-methods
    """A mixin that adds tests for the "duplicate upload" test cases.

    Consider the following procedure:

    1. Create a new feed-less repository of any content unit type.
    2. Upload a content unit into the repository.
    3. Upload the same content unit into the same repository.

    The second upload should silently fail for all Pulp releases in the 2.x
    series. See:

    * https://pulp.plan.io/issues/1406
    * https://github.com/PulpQE/pulp-smash/issues/81

    This mixin adds tests for this case. Child classes should do the following:

    * Create a repository. Content units will be uploaded into this repository.
    * Create a class or instance attribute named ``upload_import_unit_args``.
      It should be an iterable whose contents match the signature of
      :meth:`upload_import_unit`.
    """

    def test_01_first_upload(self):
        """Upload a content unit to a repository."""
        call_report = upload_import_unit(*self.upload_import_unit_args)
        self.assertIsNone(call_report['result'])

    def test_02_second_upload(self):
        """Upload the same content unit to the same repository."""
        call_report = upload_import_unit(*self.upload_import_unit_args)
        self.assertIsNone(call_report['result'])


def reset_squid(cfg):
    """Stop Squid, reset its cache directory, and restart it.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
        host.
    :returns: Nothing.
    """
    squid_version = _get_squid_version(cfg)
    svc_mgr = cli.GlobalServiceManager(cfg)
    svc_mgr.stop(('squid',))

    # Remove and re-initialize the cache directory.
    sudo = () if is_root(cfg) else ('sudo',)
    client = cli.Client(cfg)
    client.run(sudo + ('rm', '-rf', '/var/spool/squid'))
    client.run(sudo + (
        'mkdir', '--context=system_u:object_r:squid_cache_t:s0', '--mode=750',
        '/var/spool/squid'))
    client.run(sudo + ('chown', 'squid:squid', '/var/spool/squid'))
    if squid_version < Version('4'):
        client.run(sudo + ('squid', '-z'))
    else:
        client.run(sudo + ('squid', '-z', '--foreground'))

    svc_mgr.start(('squid',))


def _get_squid_version(cfg):
    """Get Squid's version, as a ``packaging.version.Version`` object."""
    # The --version option was added in Squid 4.
    resp = cli.Client(cfg).run(('squid', '-v'))
    # The first line of output is 'Squid Cache: Version ...' for at least Squid
    # 3 and 4, and at least Fedora 24, Fedora 25, RHEL 6.8 and RHEL 7.3.
    phrase = 'squid cache: version '
    return Version(resp.stdout.splitlines()[0].lower()[len(phrase):].strip())


def skip_if_type_is_unsupported(unit_type_id, server_config=None):
    """Raise ``SkipTest`` if support for the named type is not availalble.

    :param unit_type_id: A content unit type ID, such as "ostree".
    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp server being targeted. If none is provided, the config
        returned by :func:`pulp_smash.config.get_config` is used.
    :raises: ``unittest.SkipTest`` if support is unavailable.
    :returns: Nothing.
    """
    if server_config is None:
        server_config = config.get_config()
    if unit_type_id not in get_unit_type_ids(server_config):
        raise unittest.SkipTest(
            'These tests require support for the "{}" content unit type.'
            .format(unit_type_id)
        )


def get_unit_type_ids(server_config):
    """Tell which content unit types are supported by the target Pulp server.

    Each Pulp plugin adds one (or more?) content unit types to Pulp, and each
    content unit type has a unique identifier. For example, the Python plugin
    [1]_ adds the Python content unit type [2]_, and Python content units have
    an ID of ``python_package``. This function queries the server and returns
    those unit type IDs.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp deployment being targeted.
    :returns: A set of content unit type IDs. For example: ``{'ostree',
        'python_package'}``.

    .. [1] http://docs.pulpproject.org/plugins/pulp_python/
    .. [2]
       http://docs.pulpproject.org/plugins/pulp_python/reference/python-type.html
    """
    unit_types = api.Client(server_config).get(PLUGIN_TYPES_PATH).json()
    return {unit_type['id'] for unit_type in unit_types}


def sync_repo(cfg, repo):
    """Sync a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param repo: A dict of detailed information about the repository to be
        published.
    :returns: The server's reponse. Call ``.json()`` on the response to get a
        call report.
    """
    return api.Client(cfg).post(urljoin(repo['_href'], 'actions/sync/'))


def get_sha256_checksum(url):
    """Return the sha256 checksum of the file at the given URL.

    When a URL is encountered for the first time, do the following:

    1. Download the file and calculate its sha256 checksum.
    2. Cache the URL-checksum pair.
    3. Return the checksum.

    On subsequent calls, return a cached checksum.
    """
    # URLs are normalized before checking the cache and possibly downloading
    # files. Otherwise, unnecessary downloads and cache entries may be made.
    url = urlparse(url).geturl()
    if url not in _CHECKSUM_CACHE:
        checksum = hashlib.sha256(http_get(url)).hexdigest()
        _CHECKSUM_CACHE[url] = checksum
    return _CHECKSUM_CACHE[url]


def publish_repo(cfg, repo, json=None):
    """Publish a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param repo: A dict of detailed information about the repository to be
        published.
    :param json: Data to be encoded as JSON and sent as the request body.
        Defaults to ``{'id': repo['distributors'][0]['id']}``.
    :raises: ``ValueError`` when ``json`` is not passed, and ``repo`` does not
        have exactly one distributor.
    :returns: The server's reponse. Call ``.json()`` on the response to get a
        call report.
    """
    if json is None:
        if 'distributors' not in repo or len(repo['distributors']) != 1:
            raise ValueError(
                'No request body was passed, and the given repository does '
                'not have exactly one distributor. Repository: {}'.format(repo)
            )
        json = {'id': repo['distributors'][0]['id']}
    return api.Client(cfg).post(
        urljoin(repo['_href'], 'actions/publish/'),
        json
    )


def search_units(cfg, repo, criteria=None, response_handler=None):
    """Find content units in a ``repo``.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param repo: A dict of detailed information about the repository.
    :param criteria: A dict of criteria to pass in the search body. Defaults to
        an empty dict.
    :param response_handler: The callback function used by
        :class:`pulp_smash.api.Client` after searching. Defaults to
        :func:`pulp_smash.api.json_handler`.
    :returns: Whatever is dictated by ``response_handler``.
    """
    if criteria is None:
        criteria = {}
    if response_handler is None:
        response_handler = api.json_handler
    return api.Client(cfg, response_handler).post(
        urljoin(repo['_href'], 'search/units/'),
        {'criteria': criteria},
    )
