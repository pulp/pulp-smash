# coding=utf-8
"""Test the API's `Export Distributors` feature.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _Export Distributors:
    http://pulp-rpm.readthedocs.io/en/latest/tech-reference/export-distributor.html
"""
from __future__ import unicode_literals

import os

from dateutil.parser import parse

from pulp_smash import api, cli, selectors, utils
from pulp_smash.compat import urljoin, urlparse, urlunparse
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
    RPM_SHA256_CHECKSUM,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _has_getenforce(server_config):
    """Tell whether the ``getenforce`` executable is on the target system."""
    # When executing commands over SSH, in a non-login shell, and as a non-root
    # user, the PATH environment variable is quite short. For example:
    #
    #     /usr/lib64/qt-3.3/bin:/usr/local/bin:/usr/bin
    #
    # We cannot execute `PATH=${PATH}:/usr/sbin which getenforce` because
    # Plumbum does a good job of preventing shell expansions. See:
    # https://github.com/PulpQE/pulp-smash/issues/89
    client = cli.Client(server_config, cli.echo_handler)
    if client.run('test -e /usr/sbin/getenforce'.split()).returncode == 0:
        return True
    return False


def _run_getenforce(server_config):
    """Run ``getenforce`` on the target system. Return ``stdout.strip()``."""
    # Hard-coding a path to an executable is a Bad Idea™. We're doing this
    # it's simple (see _has_getenforce()), because Pulp is available on a
    # limited number of platforms, and because we may move to an SSH client
    # that allows for shell expansion.
    client = cli.Client(server_config)
    return client.run(('/usr/sbin/getenforce',)).stdout.strip()


def _create_distributor(server_config, repo_href):
    """Create an export distributor for the repository at ``repo_href``."""
    path = urljoin(repo_href, 'distributors/')
    body = gen_distributor()
    body['distributor_type_id'] = 'export_distributor'
    return api.Client(server_config).post(path, body).json()


class ExportDistributorTestCase(utils.BaseAPITestCase):
    """Establish we can publish a repository using an export distributor."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository. Optionally create a distributor.

        Create an export distributor only if `Pulp #1928`_ is fixed.

        .. _Pulp #1928: https://pulp.plan.io/issues/1928
        """
        super(ExportDistributorTestCase, cls).setUpClass()
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        cls.repo = api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()
        cls.resources.add(cls.repo['_href'])
        utils.sync_repo(cls.cfg, cls.repo['_href'])
        if selectors.bug_is_testable(1928, cls.cfg.version):
            cls.distributor = _create_distributor(cls.cfg, cls.repo['_href'])
        else:
            cls.distributor = None

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

        # Build the path to the ISO file. By default, the file is named like
        # so: {repo_id}-{iso_creation_time}-{iso_number}.iso
        iso_creation_time = parse(
            distributor['last_publish']
        ).strftime('%Y-%m-%dT%H.%M')
        iso_name = '{}-{}-01.iso'.format(self.repo['id'], iso_creation_time)
        path = '/pulp/exports/repos/'
        path = urljoin(path, distributor['config']['relative_url'])
        iso_path = urljoin(path, iso_name)

        # Fetch the ISO file via HTTP and HTTPS.
        client.response_handler = api.safe_handler
        url = urljoin(self.cfg.base_url, iso_path)
        for scheme in ('http', 'https'):
            url = urlunparse((scheme,) + urlparse(url)[1:])
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)

    def test_publish_to_dir(self):
        """Publish the repository to a directory on the Pulp server.

        Verify that :data:`pulp_smash.constants.RPM` is present and has a
        checksum of :data:`pulp_smash.constants.RPM_SHA256_CHECKSUM`.

        This test is skipped if selinux is installed and enabled on the target
        system an `Pulp issue 616 <https://pulp.plan.io/issues/616>`_ is open.
        """
        sudo = '' if utils.is_root(self.cfg) else 'sudo '

        # Issue 616 describes how SELinux prevents Pulp from writing to an
        # export directory. If that bug affects us, and if SELinux is enforcing
        # on the target system, then we disable SELinux for the duration of
        # this one test and re-enable it afterwards.
        client = cli.Client(self.cfg)
        if (_has_getenforce(self.cfg) and
                _run_getenforce(self.cfg).lower() == 'enforcing' and
                selectors.bug_is_untestable(616, self.cfg.version)):
            client.run((sudo + 'setenforce 0').split())
            self.addCleanup(client.run, (sudo + 'setenforce 1').split())

        # Create a custom directory, and ensure apache can create files in it.
        # We must schedule it for deletion, as Pulp doesn't do this during repo
        # removal. Due to the amount of permission twiddling done below, we use
        # root to reliably `rm -rf ${export_dir}`.
        export_dir = client.run('mktemp --directory'.split()).stdout.strip()
        self.addCleanup(client.run, (sudo + 'rm -rf {} ' + export_dir).split())
        client.run((sudo + 'chown apache ' + export_dir).split())

        # Publish into the directory
        path = urljoin(self.repo['_href'], 'actions/publish/')
        api.Client(self.cfg).post(path, {
            'id': self.distributor['id'],
            'override_config': {'export_dir': export_dir},
        })

        # Make sure *we* can read the files, and ensure at least one expected
        # RPM is present.
        uid = client.run('id -u'.split()).stdout.strip()
        client.run((sudo + 'chown -R {} {}'.format(uid, export_dir)).split())
        checksum = client.run(('sha256sum', os.path.join(
            export_dir,
            self.distributor['config']['relative_url'],
            RPM,
        ))).stdout.strip().split()[0]
        self.assertEqual(checksum, RPM_SHA256_CHECKSUM)
