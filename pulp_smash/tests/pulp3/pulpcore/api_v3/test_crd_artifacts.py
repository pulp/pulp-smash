# coding=utf-8
"""Tests that perform actions over artifacts."""
import hashlib
import unittest
from random import randint

from requests.exceptions import HTTPError

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import FILE_URL, FILE2_URL
from pulp_smash.exceptions import CalledProcessError
from pulp_smash.tests.pulp3.constants import ARTIFACTS_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_smash.tests.pulp3.utils import delete_orphans, get_auth


class ArtifactTestCase(unittest.TestCase, utils.SmokeTest):
    """Perform actions over an artifact."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        cls.artifact = {}
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.file = {'file': utils.http_get(FILE2_URL)}
        cls.sha256 = hashlib.sha256(cls.file['file']).hexdigest()

    def test_01_create(self):
        """Create an artifact by uploading a file.

        This test explores the design choice stated in `Pulp #2843`_ that an
        artifact can be created using HTTP POST with a body of request that
        contains a multipart form data.

        This test targets the following issues:

        * `Pulp #2843 <https://pulp.plan.io/issues/2843>`_
        * `Pulp Smash #726 <https://github.com/PulpQE/pulp-smash/issues/726>`_

        Do the following:

        1. Download a file in memory.
        2. Upload the just downloaded file to pulp.
        3. Verify that the checksum of the just created artifact is equal to
           the checksum of the file that was uploaded.
        """
        files = {'file': utils.http_get(FILE_URL)}
        type(self).artifact = self.client.post(ARTIFACTS_PATH, files=files)
        self.assertEqual(
            self.artifact['sha256'],
            hashlib.sha256(files['file']).hexdigest()
        )

    def test_01_create_no_match_data(self):
        """Create an artifact providing the wrong digest and size."""
        with self.assertRaises(HTTPError):
            data = {'sha256': utils.uuid4(),
                    'size': randint(0, 100)}
            self.client.post(ARTIFACTS_PATH, data=data, files=self.file)
        for artifact in self.client.get(ARTIFACTS_PATH)['results']:
            self.assertNotEqual(artifact['sha256'], self.sha256)

    def test_01_create_with_match_data(self):
        """Create an artifact providing the right digest and size."""
        data = {'sha256': self.sha256,
                'size': len(self.file['file'])}
        artifact = self.client.post(ARTIFACTS_PATH, data=data, files=self.file)
        self.assertEqual(artifact['sha256'], data['sha256'])
        self.assertEqual(artifact['size'], data['size'])

    @selectors.skip_if(bool, 'artifact', False)
    def test_02_read(self):
        """Read an artifact by its href."""
        artifact = self.client.get(self.artifact['_href'])
        for key, val in self.artifact.items():
            with self.subTest(key=key):
                self.assertEqual(artifact[key], val)

    @selectors.skip_if(bool, 'artifact', False)
    def test_03_delete(self):
        """Delete an artifact."""
        self.client.delete(self.artifact['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.artifact['_href'])


class ArtifactsDeleteFileSystemTestCase(unittest.TestCase, utils.SmokeTest):
    """Delete an artifact, it is removed from the filesystem.

    This test targets the following issues:

    * `Pulp #3508 <https://pulp.plan.io/issues/3508>`_
    * `Pulp Smash #908 <https://github.com/PulpQE/pulp-smash/issues/908>`_
    """

    def test_all(self):
        """Delete an artifact, it is removed from the filesystem.

        Do the following:

        1. Create an artifact, and verify it is present on the filesystem.
        2. Delete the artifact, and verify it is absent on the filesystem.
        """
        cfg = config.get_config()
        api_client = api.Client(cfg, api.json_handler)
        api_client.request_kwargs['auth'] = get_auth()
        cli_client = cli.Client(cfg)

        # create
        files = {'file': utils.http_get(FILE_URL)}
        artifact = api_client.post(ARTIFACTS_PATH, files=files)
        self.addCleanup(api_client.delete, artifact['_href'])
        sudo = () if utils.is_root(cfg) else ('sudo',)
        cmd = sudo + ('ls', artifact['file'])
        cli_client.run(cmd)

        # delete
        self.doCleanups()
        with self.assertRaises(CalledProcessError):
            cli_client.run(cmd)
