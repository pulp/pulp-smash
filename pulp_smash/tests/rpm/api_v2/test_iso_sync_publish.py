# coding=utf-8
"""Tests that sync and publish ISO repositories."""
import hashlib
import os
import unittest
from urllib.parse import urljoin, urlparse, urlsplit

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    FILE_FEED_COUNT,
    FILE_FEED_URL,
    FILE_URL,
    REPOSITORY_PATH,
)
from pulp_smash.tests.rpm.api_v2.utils import (
    TemporaryUserMixin,
    get_dists_by_type_id,
    set_pulp_manage_rsync,
)
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class ServeHttpsFalseTestCase(TemporaryUserMixin, unittest.TestCase):
    """Publish w/an rsync distributor when ``serve_https`` is false.

    More precisely, do the following:

    1. Create an ISO RPM repository. Ensure the repository has distributors of
       type ``iso_distributor`` and ``iso_rsync_distributor``, and ensure the
       former distributor's ``publish_https`` attribute is false.
    2. Populate the repository with some content.
    3. Publish the repository with both distributors. Assert that the ISO rsync
       distributor successfully places files on the target system.

    This test targets `Pulp #2657`_. According to this issue, the ISO rsync
    distributor will fail to publish files if the the ISO distributor has not
    published files via HTTPS.

    .. _Pulp #2657: https://pulp.plan.io/issues/2657
    """

    def setUp(self):
        """Set the ``pulp_manage_rsync`` boolean."""
        self.cfg = config.get_config()
        set_pulp_manage_rsync(self.cfg, True)

    def tearDown(self):
        """Reset the ``pulp_manage_rsync`` boolean."""
        set_pulp_manage_rsync(self.cfg, False)

    def test_all(self):
        """Publish w/an rsync distributor when ``serve_https`` is false."""
        if selectors.bug_is_untestable(2657, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2657')

        # Create a user with which to rsync files
        ssh_user, priv_key = self.make_user(self.cfg)
        ssh_identity_file = self.write_private_key(self.cfg, priv_key)

        # Create a repo
        client = api.Client(self.cfg, api.json_handler)
        body = {
            'distributors': [],
            'id': utils.uuid4(),
            'importer_config': {'feed': FILE_FEED_URL},
            'importer_type_id': 'iso_importer',
        }
        body['distributors'].append({
            'auto_publish': False,
            'distributor_config': {'serve_http': True, 'serve_https': False},
            'distributor_id': utils.uuid4(),
            'distributor_type_id': 'iso_distributor',
        })
        body['distributors'].append({
            'auto_publish': False,
            'distributor_config': {
                'predistributor_id': body['distributors'][0]['distributor_id'],
                'remote': {
                    'host': urlparse(self.cfg.base_url).netloc,
                    'root': '/home/' + ssh_user,
                    'ssh_identity_file': ssh_identity_file,
                    'ssh_user': ssh_user,
                },
            },
            'distributor_id': utils.uuid4(),
            'distributor_type_id': 'iso_rsync_distributor',
        })
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})

        # Sync and publish the repo. If Pulp #2657 hasn't been fixed,
        # publishing the iso_rsync_distributor will fail with an error like:
        #
        #     pulp.plugins.rsync.publish:ERROR: (1181-98080) rsync: link_stat
        #     "/var/lib/pulp/published/https/isos/repo-id/PULP_MANIFEST"
        #     failed: No such file or directory (2)
        #
        utils.sync_repo(self.cfg, repo)
        dists = get_dists_by_type_id(self.cfg, repo)
        utils.publish_repo(self.cfg, repo, {
            'id': dists['iso_distributor']['id'],
        })
        utils.publish_repo(self.cfg, repo, {
            'id': dists['iso_rsync_distributor']['id'],
        })

        # Verify the correct units are on the remote system.
        cli_client = cli.Client(self.cfg)
        sudo = () if utils.is_root(self.cfg) else ('sudo',)
        path = dists['iso_rsync_distributor']['config']['remote']['root']
        path = os.path.join(path, 'content/units')
        cmd = sudo + ('find', path, '-name', '*.iso')
        files = cli_client.run(cmd).stdout.strip().split('\n')
        self.assertEqual(len(files), FILE_FEED_COUNT, files)


class UploadIsoTestCase(unittest.TestCase):
    """Upload an ISO file into an ISO repository."""

    def test_all(self):  # pylint:disable=no-self-use
        """Upload an ISO file into an ISO repository.

        Specifically, do the following:

        1. Create an ISO repository.
        2. Upload :data:`pulp_smash.constants.FILE_URL` to the repository.
        3. Publish the repository.
        4. Download the published ISO, and assert it's equal to the uploaded
           ISO.
        """
        # create a repo
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        body = {
            'id': utils.uuid4(),
            'importer_type_id': 'iso_importer',
            'distributors': [{
                'auto_publish': False,
                'distributor_id': utils.uuid4(),
                'distributor_type_id': 'iso_distributor',
            }],
        }
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})

        # upload an ISO to the repository
        iso = utils.http_get(FILE_URL)
        iso_name = os.path.basename(urlsplit(FILE_URL).path)
        utils.upload_import_unit(cfg, iso, {
            'unit_type_id': 'iso',
            'unit_key': {
                'checksum': hashlib.sha256(iso).hexdigest(),
                'name': iso_name,
                'size': len(iso),
            },
        }, repo)

        # publish the repository, and get the published ISO
        utils.publish_repo(cfg, repo)
        client.response_handler = api.safe_handler
        path = urljoin(urljoin('/pulp/isos/', repo['id'] + '/'), iso_name)
        iso2 = client.get(path).content
        self.assertEqual(iso, iso2)
