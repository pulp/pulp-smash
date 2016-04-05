# coding=utf-8
"""Test the API's `export`_ functionality of repository.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _export:
    http://pulp-rpm.readthedocs.org/en/latest/tech-reference/export-distributor.html#export-distributors
"""

from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401

try:
    from tempfile import TemporaryDirectory
except ImportError:
    import tempfile
    import shutil
    from contextlib import contextmanager

    @contextmanager
    def TemporaryDirectory():  # pylint:disable=C0103
        """Compatibility contextmanager for temporary directory."""
        path = tempfile.mkdtemp()
        yield path
        shutil.rmtree(path)

import os
import datetime
from pulp_smash import api, utils
from pulp_smash.constants import (
    CONTENT_UPLOAD_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo, gen_distributor


class ExportDefaultDirTestCase(utils.BaseAPITestCase):
    """Establish that we can export the repository to the default directory."""

    @classmethod
    def setUpClass(cls):
        """Export the repository as an ISO to the default directory.

        Do the following:
        1. Create a repository with a valid feed
        2. Sync it
        3. Add distributor and export the repository
        4. Download recently created ISO file
        """
        super(ExportDefaultDirTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.responses = {}

        # Create a repo with a valid feed
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])

        # Sync the repo
        syncing_path = urljoin(repo['_href'], 'actions/sync/')
        client.post(syncing_path)

        # Add export distributor
        distributor = gen_distributor()
        distributor['distributor_type_id'] = 'export_distributor'
        client.post(urljoin(repo['_href'], 'distributors/'), distributor)
        # Export the repository
        cls.responses['export'] = client.post(
            urljoin(repo['_href'], 'actions/publish/'),
            {'id': distributor['distributor_id']}
        )

        # Name of the ISO file by default is as follows:
        # <repo_id>-<time_of_iso_creation>-<number_of_the_iso>.iso
        task_path = cls.responses['export'].json()['spawned_tasks'][0]['_href']
        task_details = client.get(task_path).json()
        iso_creation_time = datetime.datetime.strptime(
            task_details['finish_time'], '%Y-%m-%dT%H:%M:%SZ'
        ).strftime('%Y-%m-%dT%H.%M')
        iso_name = '{}-{}-01.iso'.format(repo['id'], iso_creation_time)

        # Download recently exported repository
        relative_url = distributor['distributor_config']['relative_url']
        download_path = urljoin(
            '/pulp/exports/repos/', relative_url + iso_name
        )
        cls.responses['download'] = client.get(download_path)
        cls.status_codes = {'export': 202, 'download': 200}

    def test_status_code(self):
        """Assert each response has a correct HTTP status code."""
        for key, response in self.responses.items():
            with self.subTest(key=key):
                self.assertEqual(response.status_code, self.status_codes[key])


class ExportCustomDirTestCase(utils.BaseAPITestCase):
    """Establish that we can export the repository to the custom directory."""

    @classmethod
    def setUpClass(cls):
        """Export the repository to the custom directory.

        It will be exported as a directory, not as an ISO file.

        Do the following:
        1. Create a repository without a feed
        2. Download RPM file and upload it to the repository
        3. Add distributor and export the repository to the custom directory
        4. Read exported RPM file from the custom directory
        """
        super(ExportCustomDirTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        cls.responses = {}

        # Create a repo without feed
        body = gen_repo()
        repo = client.post(REPOSITORY_PATH, body).json()
        cls.resources.add(repo['_href'])

        #  Download RPM
        cls.rpm = client.get(urljoin(RPM_FEED_URL, RPM)).content

        # Upload RPM and import it to the repository
        malloc = client.post(CONTENT_UPLOAD_PATH).json()
        client.put(urljoin(malloc['_href'], '0/'), data=cls.rpm)
        client.post(urljoin(repo['_href'], 'actions/import_upload/'), {
            'unit_key': {},
            'unit_type_id': 'rpm',
            'upload_id': malloc['upload_id'],
        })
        client.delete(malloc['_href'])

        # Add export distributor
        distributor = gen_distributor()
        distributor['distributor_type_id'] = 'export_distributor'
        client.post(urljoin(repo['_href'], 'distributors/'), distributor)
        relative_url = distributor['distributor_config']['relative_url'][:-1]

        # Create temporary directory, set ACL for apache user to be able to
        # export the repository to this directory. Also set default ACL for
        # current user to be able to remove directory after this test.
        # Currently Pulp does not clean up custom export directory during
        # repository removal.
        with TemporaryDirectory() as cls.custom_dir:
            os.system('setfacl -m u:apache:rwx {}'.format(cls.custom_dir))
            os.system('setfacl -m d:{}:rwx {}'.format(
                os.getlogin(), cls.custom_dir
            ))
            cls.exported_rpm = None

            # Export the repository
            cls.responses['export'] = client.post(
                urljoin(repo['_href'], 'actions/publish/'), {
                    'id': distributor['distributor_id'],
                    'override_config': {'export_dir': cls.custom_dir}
                }
            )

            # Read the RPM from the custom directory
            exported_rpm_path = os.path.join(cls.custom_dir, relative_url, RPM)
            try:
                with open(exported_rpm_path) as rpm_file:
                    cls.exported_rpm = rpm_file.read()
            except IOError:
                pass

    def test_status_code(self):
        """Assert the response has a correct HTTP status code."""
        self.assertEqual(self.responses['export'].status_code, 202)

    def test_custom_dir_export(self):
        """Assert the repository was exported to the custom directory."""
        self.assertEqual(self.rpm, self.exported_rpm)
