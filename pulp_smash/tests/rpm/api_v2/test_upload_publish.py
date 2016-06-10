# coding=utf-8
"""Tests that upload to and publish RPM repositories.

For information on repository upload and publish operations, see `Uploading
Content`_ and `Publication`_.

.. _Publication:
    http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/repo/publish.html
.. _Uploading Content:
    http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/upload.html
"""
from __future__ import unicode_literals

from itertools import product

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import (
    CALL_REPORT_KEYS,
    CONTENT_UPLOAD_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class UploadRpmTestCase(utils.BaseAPITestCase):
    """Test whether one can upload, associate and publish RPMs."""

    @classmethod
    def setUpClass(cls):
        """Upload an RPM to a repo, copy it to another, publish and download.

        Do the following:

        1. Create two RPM repositories, both without feeds.
        2. Upload an RPM to the first repository.
        3. Associate the first repository with the second, causing the RPM to
           be copied.
        4. Add a distributor to both repositories and publish them.
        """
        super(UploadRpmTestCase, cls).setUpClass()
        utils.reset_pulp(cls.cfg)  # See: https://pulp.plan.io/issues/1406
        cls.responses = {}

        # Download an RPM and create two repositories.
        client = api.Client(cls.cfg, api.json_handler)
        repos = [client.post(REPOSITORY_PATH, gen_repo()) for _ in range(2)]
        for repo in repos:
            cls.resources.add(repo['_href'])
        client.response_handler = api.safe_handler
        cls.rpm = utils.http_get(RPM_URL)

        # Begin an upload request, upload an RPM, move the RPM into a
        # repository, and end the upload request.
        cls.responses['malloc'] = client.post(CONTENT_UPLOAD_PATH)
        cls.responses['upload'] = client.put(
            urljoin(cls.responses['malloc'].json()['_href'], '0/'),
            data=cls.rpm,
        )
        cls.responses['import'] = client.post(
            urljoin(repos[0]['_href'], 'actions/import_upload/'),
            {
                'unit_key': {},
                'unit_type_id': 'rpm',
                'upload_id': cls.responses['malloc'].json()['upload_id'],
            },
        )
        cls.responses['free'] = client.delete(
            cls.responses['malloc'].json()['_href'],
        )

        # Copy content from the first repository to the second.
        cls.responses['copy'] = client.post(
            urljoin(repos[1]['_href'], 'actions/associate/'),
            {'source_repo_id': repos[0]['id']}
        )

        # Add a distributor to and publish both repositories.
        cls.responses['distribute'] = []
        cls.responses['publish'] = []
        for repo in repos:
            cls.responses['distribute'].append(client.post(
                urljoin(repo['_href'], 'distributors/'),
                gen_distributor(),
            ))
            cls.responses['publish'].append(client.post(
                urljoin(repo['_href'], 'actions/publish/'),
                {'id': cls.responses['distribute'][-1].json()['id']},
            ))

        # Search for all units in each of the two repositories.
        body = {'criteria': {}}
        cls.responses['repo units'] = [
            client.post(urljoin(repo['_href'], 'search/units/'), body)
            for repo in repos
        ]

    def test_status_code(self):
        """Verify the HTTP status code of each server response."""
        for step, code in (
                ('malloc', 201),
                ('upload', 200),
                ('import', 202),
                ('free', 200),
                ('copy', 202),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)
        for step, code in (
                ('distribute', 201),
                ('publish', 202),
                ('repo units', 200),
        ):
            with self.subTest(step=step):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)

    def test_malloc(self):
        """Verify the response body for `creating an upload request`_.

        .. _creating an upload request:
           http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/upload.html#creating-an-upload-request
        """
        keys = set(self.responses['malloc'].json().keys())
        self.assertLessEqual({'_href', 'upload_id'}, keys)

    def test_upload(self):
        """Verify the response body for `uploading bits`_.

        .. _uploading bits:
           http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/upload.html#upload-bits
        """
        self.assertIsNone(self.responses['upload'].json())

    def test_call_report_keys(self):
        """Verify each call report has a sane structure.

        * `Import into a Repository
          <http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/upload.html#import-into-a-repository>`_
        * `Copying Units Between Repositories
          <http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/associate.html#copying-units-between-repositories>`_
        """
        for step in {'import', 'copy'}:
            with self.subTest(step=step):
                keys = frozenset(self.responses[step].json().keys())
                self.assertLessEqual(CALL_REPORT_KEYS, keys)

    def test_call_report_errors(self):
        """Verify each call report is error-free."""
        for step, key in product({'import', 'copy'}, {'error', 'result'}):
            with self.subTest((step, key)):
                self.assertIsNone(self.responses[step].json()[key])

    def test_free(self):
        """Verify the response body for ending an upload.

        `Delete an Upload Request
        <http://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/content/upload.html#delete-an-upload-request>`_
        """
        self.assertIsNone(self.responses['free'].json())

    def test_publish_keys(self):
        """Verify publishing a repository generates a call report."""
        for i, response in enumerate(self.responses['publish']):
            with self.subTest(i=i):
                keys = frozenset(response.json().keys())
                self.assertLessEqual(CALL_REPORT_KEYS, keys)

    def test_publish_errors(self):
        """Verify publishing a call report doesn't generate any errors."""
        for i, response in enumerate(self.responses['publish']):
            for key in {'error', 'result'}:
                with self.subTest((i, key)):
                    self.assertIsNone(response.json()[key])

    def test_repo_units_consistency(self):
        """Verify the two repositories have the same content units."""
        bodies = [resp.json() for resp in self.responses['repo units']]
        self.assertEqual(
            set(unit['unit_id'] for unit in bodies[0]),  # This test is fragile
            set(unit['unit_id'] for unit in bodies[1]),  # due to hard-coded
        )  # indices. But the data is complex, and this makes things simpler.

    def test_unit_integrity(self):
        """Download and verify an RPM from each Pulp distributor."""
        for response in self.responses['distribute']:
            distributor = response.json()
            with self.subTest(distributor=distributor):
                url = urljoin(
                    '/pulp/repos/',
                    response.json()['config']['relative_url']
                )
                url = urljoin(url, RPM)
                rpm = api.Client(self.cfg).get(url).content
                self.assertEqual(rpm, self.rpm)
