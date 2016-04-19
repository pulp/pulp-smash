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
    PYTHON_EGG_URL,
    REPOSITORY_PATH,
)
from pulp_smash.tests.python.api_v2.utils import gen_repo


def _upload_import_python_package(server_config, python_package, repo_href):
    """Upload a Python package and import it into a repository.

    Return the JSON-decoded body of the call report received when importing the
    Python package.
    """
    client = api.Client(server_config, api.json_handler)
    malloc = client.post(CONTENT_UPLOAD_PATH)
    client.put(urljoin(malloc['_href'], '0/'), data=python_package)
    call_report = client.post(urljoin(repo_href, 'actions/import_upload/'), {
        'unit_key': {},
        'unit_type_id': 'python_package',
        'upload_id': malloc['upload_id'],
    })
    client.delete(malloc['_href'])
    return call_report


class DuplicateUploadsTestCase(utils.BaseAPITestCase):
    """Test how well Pulp can deal with duplicate uploads."""

    @classmethod
    def setUpClass(cls):
        """Create a Python repo. Upload a Python package into it twice."""
        super(DuplicateUploadsTestCase, cls).setUpClass()

        # Download content.
        client = api.Client(cls.cfg)
        python_package = utils.http_get(PYTHON_EGG_URL)

        # Create a feed-less repository.
        client.response_handler = api.json_handler
        repo = client.post(REPOSITORY_PATH, gen_repo())
        cls.resources.add(repo['_href'])

        # Upload and import the python package into the repository, twice.
        cls.call_reports = tuple((
            _upload_import_python_package(
                cls.cfg,
                python_package,
                repo['_href'],
            )
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
