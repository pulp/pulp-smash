# coding=utf-8
"""Test the API's `Export Distributors` feature.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _Export Distributors:
    http://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/export-distributor.html
"""
import inspect
import os
import unittest
from urllib.parse import urljoin, urlparse, urlunparse
from xml.dom import minidom

from dateutil.parser import parse
from packaging.version import Version

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    REPOSITORY_EXPORT_DISTRIBUTOR,
    REPOSITORY_GROUP_EXPORT_DISTRIBUTOR,
    REPOSITORY_GROUP_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
    RPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    DisableSELinuxMixin,
    gen_distributor,
    gen_repo,
    gen_repo_group,
)
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Possibly skip the tests in this module.

    Skip this module of tests if Pulp suffers from `issue 2277
    <https://pulp.plan.io/issues/2277>`_.
    """
    set_up_module()
    if selectors.bug_is_untestable(2277, config.get_config().version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2277')


def _create_distributor(
        server_config, href, distributor_type_id, checksum_type=None):
    """Create an export distributor for the entity at ``href``."""
    path = urljoin(href, 'distributors/')
    body = gen_distributor()
    body['distributor_type_id'] = distributor_type_id
    if checksum_type is not None:
        body['distributor_config']['checksum_type'] = checksum_type
    return api.Client(server_config).post(path, body).json()


def _get_iso_url(cfg, entity, entity_type, distributor):
    """Build the URL to the ISO file.

    By default, the file is named like so:
    {repo_id}-{iso_creation_time}-{iso_number}.iso
    """
    iso_name = '{}-{}-01.iso'.format(
        entity['id'],
        parse(distributor['last_publish']).strftime('%Y-%m-%dT%H.%M')
    )
    path = '/pulp/exports/{}/'.format(entity_type)
    path = urljoin(path, distributor['config']['relative_url'])
    iso_path = urljoin(path, iso_name)
    return urljoin(cfg.base_url, iso_path)


class ExportDirMixin(DisableSELinuxMixin):
    """Mixin with repo export to dir utilities.

    A mixin with methods for managing an export directory on a Pulp server.
    This mixin is designed to support the following work flow:

    1. Create a directory. (See :meth:`create_export_dir`.)
    2. Export a repository to the directory.
    3. Make the directory readable. (See :meth:`change_export_dir_owner`.)
    4. Inspect the contents of the directory.

    :meth:`publish_to_dir` conveniently executes steps 1–3. Consider using the
    other methods only if more granularity is needed.

    A class attribute named ``cfg`` must be present. It should be a
    :class:`pulp_smash.config.ServerConfig`.
    """

    def __init__(self, *args, **kwargs):
        """Initialize variables."""
        self.__sudo = None
        super(ExportDirMixin, self).__init__(*args, **kwargs)

    def sudo(self):
        """Return either ``''`` or ``'sudo '``.

        Return the former if root, and the latter if not.
        """
        if self.__sudo is None:
            self.__sudo = '' if utils.is_root(self.cfg) else 'sudo '
        return self.__sudo

    def create_export_dir(self):
        """Create a directory, and ensure Pulp can export to it.

        Create a directory, and set its owner and group to ``apache``. If `Pulp
        issue 616`_ affects the current Pulp system, disable SELinux, and
        schedule a clean-up command that re-enables SELinux.

        .. WARNING:: Only call this method from a unittest ``test*`` method. If
            called from elsewhere, SELinux may be left disabled.

        :returns: The path to the created directory, as a string.
        """
        # Issue 616 describes how SELinux prevents Pulp from writing to an
        # export directory. If that bug affects us, and if SELinux is present
        # and enforcing on the target system, then we disable SELinux for the
        # duration of this one test and re-enable it afterwards.
        self.maybe_disable_selinux(self.cfg, 616)

        # Create a custom directory, and ensure apache can create files in it.
        # We must schedule it for deletion, as Pulp doesn't do this during repo
        # removal. Due to the amount of permission twiddling done below, we use
        # root to reliably `rm -rf ${export_dir}`.
        client = cli.Client(self.cfg)
        export_dir = client.run('mktemp --directory'.split()).stdout.strip()
        self.addCleanup(
            client.run, (self.sudo() + 'rm -rf {} ' + export_dir).split())
        client.run((self.sudo() + 'chown apache ' + export_dir).split())
        return export_dir

    def change_export_dir_owner(self, export_dir):
        """Change the owner to the running Pulp Smash user.

        Update the remote path ``dir`` owner to the user running Pulp Smash.
        """
        client = cli.Client(self.cfg)
        uid = client.run('id -u'.split()).stdout.strip()
        client.run(
            (self.sudo() + 'chown -R {} {}'.format(uid, export_dir)).split())

    def publish_to_dir(self, entity_href, distributor_id):
        """Create an export directory, publish to it, and change its owner.

        For details, see :class:`ExportDirMixin`.

        :param entity_href: The path to an entity such as a repository or a
            repository group.
        :param distributor_id: The ID of the distributor to use when exporting.
        :returns: The path to the export directory.
        """
        export_dir = self.create_export_dir()
        api.Client(self.cfg).post(urljoin(entity_href, 'actions/publish/'), {
            'id': distributor_id,
            'override_config': {'export_dir': export_dir},
        })
        self.change_export_dir_owner(export_dir)
        return export_dir


class BaseExportChecksumTypeTestCase(ExportDirMixin, utils.BaseAPITestCase):
    """Base class for repo and repo group export with checksum type tests."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository.

        Also skips the test if Pulp version less than 2.9.

        Children of this base class must provide a ``distributors`` attribute
        with the list of distributors to export a repository or repository
        group.
        """
        if inspect.getmro(cls)[0] == BaseExportChecksumTypeTestCase:
            raise unittest.SkipTest('Abstract base class.')
        super(BaseExportChecksumTypeTestCase, cls).setUpClass()
        if cls.cfg.version < Version('2.9'):
            raise unittest.SkipTest('This test requires Pulp 2.9 or newer')
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        cls.repo = api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()
        cls.resources.add(cls.repo['_href'])
        utils.sync_repo(cls.cfg, cls.repo['_href'])

    def _publish_to_web(self, entity, distributor):
        """Publish ``entity`` to web using the ``distributor``.

        Return the updated distributor information.
        """
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(entity['_href'], 'actions/publish/')
        client.post(path, {'id': distributor['id']})
        return client.get(distributor['_href'])

    def _assert_checksum_type(self, path, checksum_type):
        """Assert repomd.xml have the proper ``checksum_type``.

        ``path`` must be the remote path of the repomd.xml file.
        """
        document = minidom.parseString(cli.Client(self.cfg).run(
            'cat {}'.format(path).split()).stdout)
        self.assertTrue(all([
            element.attributes.get('type').value == checksum_type
            for element in document.getElementsByTagName('checksum')
        ]))

    def get_export_entity(self):
        """Provide the export entity.

        The entity can be either a repository or a repository group.
        """
        raise NotImplementedError(
            'Please provide an export entity. Either a repository or a '
            'repository group.'
        )

    def get_repomd_publish_path(self, export_dir, distributor):
        """Provide the repomd.xml publish path.

        Repository and repository group exports have a different path to
        repomd.xml file.
        """
        raise NotImplementedError(
            'Please provide the repomd.xml publish path.')

    def get_repomd_iso_publish_path(self, export_dir, distributor):
        """Provide the repomd.xml publish path within an exported ISO.

        Repository and repository group exports have a different path to
        repomd.xml file within the exported ISO.
        """
        raise NotImplementedError(
            'Please provide the repomd.xml ISO publish path.')

    def get_export_entity_type(self):
        """Provide the export entity type.

        Return ``repos`` for repository and ``repo_group`` for repository
        group.
        """
        raise NotImplementedError(
            'Please provide the export entity type: ``repos`` for repository '
            'and ``repo_group`` for repository group.'
        )

    def test_publish_to_dir_checksum_type(self):  # pylint:disable=invalid-name
        """Publish to a directory choosing the checksum type."""
        for distributor in self.distributors:  # pylint:disable=no-member
            checksum_type = distributor['config']['checksum_type']
            with self.subTest(msg=checksum_type):
                export_dir = self.publish_to_dir(
                    self.get_export_entity()['_href'],
                    distributor['id'],
                )
                self._assert_checksum_type(
                    self.get_repomd_publish_path(export_dir, distributor),
                    checksum_type
                )

    def test_publish_to_web_checksum_type(self):  # pylint:disable=invalid-name
        """Publish to web choosing the checksum type."""
        client = cli.Client(self.cfg)
        for distributor in self.distributors:  # pylint:disable=no-member
            checksum_type = distributor['config']['checksum_type']
            with self.subTest(msg=checksum_type):
                distributor = self._publish_to_web(
                    self.get_export_entity(), distributor)
                url = _get_iso_url(
                    self.cfg,
                    self.get_export_entity(),
                    self.get_export_entity_type(),
                    distributor
                )
                export_dir = client.run(
                    'mktemp --directory'.split()).stdout.strip()
                iso_path = client.run('mktemp'.split()).stdout.strip()
                self.addCleanup(
                    client.run,
                    '{}rm -rf {} {}'.format(
                        self.sudo(), export_dir, iso_path
                    ).split()
                )
                client.run(
                    'curl --insecure -o {} {}'.format(iso_path, url).split())
                client.run((self.sudo() + 'mount -o loop {} {}'.format(
                    iso_path, export_dir)).split())
                self.addCleanup(
                    client.run,
                    (self.sudo() + 'umount {}'.format(export_dir)).split()
                )
                self._assert_checksum_type(
                    self.get_repomd_iso_publish_path(export_dir, distributor),
                    checksum_type
                )


class ExportChecksumTypeTestCase(BaseExportChecksumTypeTestCase):
    """Publish a repository choosing the distributor checksum type."""

    @classmethod
    def setUpClass(cls):
        """Create some distributors.

        Each distributor is configured with a valid checksum type.
        """
        super(ExportChecksumTypeTestCase, cls).setUpClass()
        cls.distributors = [
            _create_distributor(
                cls.cfg, cls.repo['_href'],
                REPOSITORY_EXPORT_DISTRIBUTOR,
                checksum_type
            )
            for checksum_type in ('md5', 'sha1', 'sha256')
        ]

    def get_export_entity(self):
        """Provide the export entity."""
        return self.repo

    def get_repomd_publish_path(self, export_dir, distributor):
        """Provide the repomd.xml publish path."""
        return os.path.join(
            export_dir,
            distributor['config']['relative_url'],
            'repodata',
            'repomd.xml'
        )

    def get_export_entity_type(self):
        """Provide the export entity type."""
        return 'repos'

    def get_repomd_iso_publish_path(self, export_dir, distributor):
        """Provide the repomd.xml publish path within an exported ISO."""
        return os.path.join(
            export_dir,
            distributor['config']['relative_url'],
            'repodata',
            'repomd.xml'
        )


class RepoGroupExportChecksumTypeTestCase(BaseExportChecksumTypeTestCase):
    """Publish a repository group choosing the distributor checksum type."""

    @classmethod
    def setUpClass(cls):
        """Create required entities for publishing a repository group.

        Do the following:

        1. Create a repository group and add the repository created by super
           call.
        2. Creates some distributors. Each distributor is configured with a
           valid checksum type.
        """
        super(RepoGroupExportChecksumTypeTestCase, cls).setUpClass()
        body = gen_repo_group()
        body['repo_ids'] = [cls.repo['id']]
        cls.repo_group = api.Client(cls.cfg).post(
            REPOSITORY_GROUP_PATH, body).json()
        cls.resources.add(cls.repo_group['_href'])
        cls.distributors = [
            _create_distributor(
                cls.cfg,
                cls.repo_group['_href'],
                REPOSITORY_GROUP_EXPORT_DISTRIBUTOR,
                checksum_type
            )
            for checksum_type in ('md5', 'sha1', 'sha256')
        ]

    def get_export_entity(self):
        """Provide the export entity."""
        return self.repo_group

    def get_repomd_publish_path(self, export_dir, distributor):
        """Provide the repomd.xml publish path."""
        return os.path.join(
            export_dir,
            distributor['config']['relative_url'],
            self.repo['id'],
            'repodata',
            'repomd.xml'
        )

    def get_export_entity_type(self):
        """Provide the export entity type."""
        return 'repo_group'

    def get_repomd_iso_publish_path(self, export_dir, distributor):
        """Provide the repomd.xml publish path within an exported ISO."""
        return os.path.join(
            export_dir,
            self.repo['id'],
            'repodata',
            'repomd.xml'
        )


class ExportDistributorTestCase(ExportDirMixin, utils.BaseAPITestCase):
    """Establish we can publish a repository using an export distributor."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository. Optionally create a distributor.

        Skip creating the distributor if we are testing Pulp 2.9 and it is
        affected by `Pulp #1928`_.

        .. _Pulp #1928: https://pulp.plan.io/issues/1928
        """
        super(ExportDistributorTestCase, cls).setUpClass()
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        cls.repo = api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()
        cls.resources.add(cls.repo['_href'])
        utils.sync_repo(cls.cfg, cls.repo['_href'])
        if (cls.cfg.version >= Version('2.9') and
                selectors.bug_is_untestable(1928, cls.cfg.version)):
            cls.distributor = None
        else:
            cls.distributor = _create_distributor(
                cls.cfg, cls.repo['_href'], REPOSITORY_EXPORT_DISTRIBUTOR)

    def setUp(self):
        """Optionally create an export distributor.

        Create an export distributor only if one is not already present. (See
        :meth:`setUpClass`.)
        """
        super(ExportDistributorTestCase, self).setUp()
        if self.distributor is None:
            self.distributor = _create_distributor(
                self.cfg,
                self.repo['_href'],
                REPOSITORY_EXPORT_DISTRIBUTOR
            )

    def test_publish_to_web(self):
        """Publish the repository to the web, and fetch the ISO file.

        The ISO file should be available over both HTTP and HTTPS. Fetch it
        from both locations, and assert that the fetch was successful.
        """
        # Publish the repository, and re-read the distributor.
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(self.repo['_href'], 'actions/publish/')
        client.post(path, {'id': self.distributor['id']})
        distributor = client.get(self.distributor['_href'])

        # Fetch the ISO file via HTTP and HTTPS.
        client.response_handler = api.safe_handler
        url = _get_iso_url(self.cfg, self.repo, 'repos', distributor)
        for scheme in ('http', 'https'):
            url = urlunparse((scheme,) + urlparse(url)[1:])
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)

    def test_publish_to_dir(self):
        """Publish the repository to a directory on the Pulp server.

        gerify that :data:`pulp_smash.constants.RPM` is present and has a
        correct checksum.

        This test is skipped if selinux is installed and enabled on the target
        system an `Pulp issue 616 <https://pulp.plan.io/issues/616>`_ is open.
        """
        export_dir = self.publish_to_dir(
            self.repo['_href'],
            self.distributor['id'],
        )
        actual = cli.Client(self.cfg).run(('sha256sum', os.path.join(
            export_dir,
            self.distributor['config']['relative_url'],
            RPM,
        ))).stdout.strip().split()[0]
        expect = utils.get_sha256_checksum(RPM_URL)
        self.assertEqual(actual, expect)
