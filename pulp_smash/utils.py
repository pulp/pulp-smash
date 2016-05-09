# coding=utf-8
"""Utility functions for Pulp tests.

This module may make use of :mod:`pulp_smash.api` and :mod:`pulp_smash.cli`,
but the reverse should not be done.
"""
from __future__ import unicode_literals

import io
import uuid

import requests
import unittest2

from pulp_smash import api, cli, config, exceptions
from pulp_smash.compat import urljoin
from pulp_smash.constants import (
    CONTENT_UPLOAD_PATH,
    ORPHANS_PATH,
    PLUGIN_TYPES_PATH,
    PULP_SERVICES,
    REPOSITORY_PATH,
)


def uuid4():
    """Return a random UUID, as a unicode string."""
    return type('')(uuid.uuid4())


# See design discussion at: https://github.com/PulpQE/pulp-smash/issues/31
def get_broker(server_config):
    """Build an object for managing the target system's AMQP broker.

    Talk to the host named by ``server_config`` and use simple heuristics to
    determine which AMQP broker is installed. If Qpid or RabbitMQ appear to be
    installed, return a :class:`pulp_smash.cli.Service` object for managing
    those services respectively. Otherwise, raise an exception.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        system on which an AMQP broker exists.
    :rtype: pulp_smash.cli.Service
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
            return cli.Service(server_config, executable)
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

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :return: The completed process.
    :rtype: pulp_smash.cli.CompletedProcess
    """
    cmd = 'pulp-admin login -u {} -p {}'.format(*server_config.auth).split()
    return cli.Client(server_config).run(cmd)


def reset_pulp(server_config):
    """Stop Pulp, reset its database, remove certain files, and start it.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: Nothing.
    """
    services = tuple((
        cli.Service(server_config, service) for service in PULP_SERVICES
    ))
    for service in services:
        service.stop()

    # Reset the database and nuke accumulated files.
    client = cli.Client(server_config)
    prefix = '' if is_root(server_config) else 'sudo '
    client.run('mongo pulp_database --eval db.dropDatabase()'.split())
    client.run('sudo -u apache pulp-manage-db'.split())
    client.run((prefix + 'rm -rf /var/lib/pulp/content').split())
    client.run((prefix + 'rm -rf /var/lib/pulp/published').split())

    for service in services:
        service.start()


def upload_import_unit(server_config, unit, unit_type_id, repo_href):
    """Upload a content unit to a Pulp server and import it into a repository.

    This procedure works for *some* unit types, such as ``rpm`` or
    ``puppet_package``. Others, like ``package_group``, require an alternate
    procedure.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param unit: A binary blob that can be uploaded to a Pulp server and
        imported into a repository as a content unit. For example, an RPM file
        or Python package.
    :param content_type_id: The type ID of the content unit. For example,
        ``rpm`` or ``python_package``.
    :param repo_href: The path to the repository into which ``unit`` will be
        imported.
    :returns: The call report returned when importing the unit.
    """
    client = api.Client(server_config, api.json_handler)
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

    call_report = client.post(urljoin(repo_href, 'actions/import_upload/'), {
        'unit_key': {},
        'unit_type_id': unit_type_id,
        'upload_id': malloc['upload_id'],
    })
    client.delete(malloc['_href'])
    return call_report


class BaseAPITestCase(unittest2.TestCase):
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
            A :class:`pulp_smash.config.ServerConfig` object.
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


class BaseAPICrudTestCase(unittest2.TestCase):
    """A parent class for API CRUD test cases.

    :meth:`create_body` and :meth:`update_body` should be overridden by
    concrete child classes. The bodies of these two methods are encoded to JSON
    and used as the bodies of HTTP requests for creating and updating a
    repository, respectively. Be careful to return appropriate data when
    overriding these methods: the various ``test*`` methods assume the
    repository is fairly simple.

    Relevant Pulp documentation:

    Create
        http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/cud.html#create-a-repository
    Read
        http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/retrieval.html#retrieve-a-single-repository
    Update
        http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/cud.html#update-a-repository
    Delete
        http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/cud.html#delete-a-repository
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

    This mixin adds tests for this case. This mixin requires an attribute named
    ``call_reports`` be present, where this attribute is an iterable of the
    call reports produced by steps 2 and 3, above.
    """

    def test_call_report_result(self):
        """Assert each call report's "result" field is null.

        Other checks are done automatically by
        :func:`pulp_smash.api.json_handler`. See it for details.
        """
        for i, call_report in enumerate(self.call_reports):
            with self.subTest(i=i):
                self.assertIsNone(call_report['result'])


def reset_squid(server_config):
    """Stop Squid, reset its cache directory, and restart it.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: Nothing.
    """
    squid_service = cli.Service(server_config, 'squid')
    squid_service.stop()

    # Clean out the cache directory and reinitialize it.
    client = cli.Client(server_config)
    prefix = '' if is_root(server_config) else 'sudo '
    client.run((prefix + 'rm -rf /var/spool/squid').split())
    client.run((prefix + 'mkdir --context=system_u:object_r:squid_cache_t:s0' +
                ' --mode=750 /var/spool/squid').split())
    client.run((prefix + 'chown squid:squid /var/spool/squid').split())
    client.run((prefix + 'squid -z').split())

    squid_service.start()


def skip_if_type_is_unsupported(unit_type_id, server_config=None):
    """Raise ``SkipTest`` if support for the named type is not availalble.

    :param unit_type_id: A content unit type ID, such as "ostree".
    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted. If none is provided, the config returned by
        :func:`pulp_smash.config.get_config` is used.
    :raises: ``unittest2.SkipTest`` if support is unavailable.
    :returns: Nothing.
    """
    if server_config is None:
        server_config = config.get_config()
    if unit_type_id not in get_unit_type_ids(server_config):
        raise unittest2.SkipTest(
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

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: A set of content unit type IDs. For example: ``{'ostree',
        'python_package'}``.

    .. [1] http://pulp-python.readthedocs.io/en/latest/
    .. [2]
        http://pulp-python.readthedocs.io/en/latest/reference/python-type.html
    """
    unit_types = api.Client(server_config).get(PLUGIN_TYPES_PATH).json()
    return {unit_type['id'] for unit_type in unit_types}


def is_root(server_config):
    """Tell if we are root on the target system.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :returns: Either ``True`` or ``False``.
    """
    if cli.Client(server_config).run(('id', '-u')).stdout.strip() == '0':
        return True
    return False


def sync_repo(server_config, href):
    """Sync the referenced repository via the API. Return the server response.

    Checks are run against the server's response. If the sync appears to have
    failed, an exception is raised.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param href: The API v2 path to the repository to sync.
    :returns: The server's response.
    """
    return api.Client(server_config).post(urljoin(href, 'actions/sync/'))
