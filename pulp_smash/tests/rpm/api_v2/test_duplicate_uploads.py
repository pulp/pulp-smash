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
from pulp_smash.constants import REPOSITORY_PATH, RPM_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class DuplicateUploadsTestCase(
        utils.BaseAPITestCase,
        utils.DuplicateUploadsMixin):
    """Test how well Pulp can deal with duplicate unit uploads."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository. Upload an RPM into it twice."""
        super(DuplicateUploadsTestCase, cls).setUpClass()
        utils.reset_pulp(cls.cfg)
        unit = utils.http_get(RPM_URL)
        unit_type_id = 'rpm'
        client = api.Client(cls.cfg, api.json_handler)
        repo_href = client.post(REPOSITORY_PATH, gen_repo())['_href']
        cls.resources.add(repo_href)
        cls.call_reports = tuple((
            utils.upload_import_unit(cls.cfg, unit, unit_type_id, repo_href)
            for _ in range(2)
        ))
