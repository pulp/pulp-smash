# coding=utf-8
"""Tests for how well Pulp can deal with duplicate uploads.

This module targets `Pulp #1406`_ and `Pulp Smash #81`_. The test procedure is
as follows:

1. Create a new feed-less repository.
2. Upload content and import it into the repository. Assert the upload and
   import was successful.
3. Upload identical content and import it into the repository.

The second upload should silently fail for all Pulp releases in the 2.x series.

.. _Pulp #1406: https://pulp.plan.io/issues/1406
.. _Pulp Smash #81: https://github.com/PulpQE/pulp-smash/issues/81
"""
from __future__ import unicode_literals

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import (
    CONTENT_UPLOAD_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_FEED_URL,
)


def _upload_import_rpm(server_config, rpm, repo_href):
    """Upload an RPM to a Pulp server and import it into a repository.

    Create an upload request, upload ``rpm``, import it into the repository at
    ``repo_href``, and close the upload request. Return the call report
    returned when importing the RPM.
    """
    client = api.Client(server_config, api.json_handler)
    malloc = client.post(CONTENT_UPLOAD_PATH)
    client.put(urljoin(malloc['_href'], '0/'), data=rpm)
    call_report = client.post(urljoin(repo_href, 'actions/import_upload/'), {
        'unit_key': {},
        'unit_type_id': 'rpm',
        'upload_id': malloc['upload_id'],
    })
    client.delete(malloc['_href'])
    return call_report


class DuplicateUploadsTestCase(utils.BaseAPITestCase):
    """Tests for how well Pulp can deal with duplicate uploads."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository. Upload the same content into it twice."""
        super(DuplicateUploadsTestCase, cls).setUpClass()
        utils.reset_pulp(cls.cfg)

        # Download content.
        client = api.Client(cls.cfg)
        cls.rpm = client.get(urljoin(RPM_FEED_URL, RPM)).content

        # Create a feed-less repository.
        client = api.Client(cls.cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, {
            'id': utils.uuid4(),
            'importer_config': {},
            'importer_type_id': 'yum_importer',
            'notes': {'_repo-type': 'rpm-repo'},
        })
        cls.resources.add(repo['_href'])

        # Upload content and import it into the repository. Do it twice!
        cls.call_reports = tuple((
            _upload_import_rpm(cls.cfg, cls.rpm, repo['_href'])
            for _ in range(2)
        ))

    def test_call_report_result(self):
        """Assert each call report's "result" field is null.

        Other checks are done automatically by
        :func:`pulp_smash.api.json_handler`. See it for details.
        """
        for i, call_report in enumerate(self.call_reports):
            with self.subTest(i=i):
                self.assertIsNone(call_report['result'])
