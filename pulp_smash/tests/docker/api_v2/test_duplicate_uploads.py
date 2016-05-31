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

import unittest2
from packaging.version import Version

from pulp_smash import api, selectors, utils
from pulp_smash.constants import DOCKER_IMAGE_URL, REPOSITORY_PATH
from pulp_smash.tests.docker.api_v2.utils import gen_repo
from pulp_smash.tests.docker.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class DuplicateUploadsTestCase(
        utils.BaseAPITestCase,
        utils.DuplicateUploadsMixin):
    """Test how well Pulp can deal with duplicate content unit uploads."""

    @classmethod
    def setUpClass(cls):
        """Create a Docker repository. Upload a Docker image into it twice.

        Skip this test if `Pulp #1957`_ affects us.

        .. _Pulp #1957: https://pulp.plan.io/issues/1957
        """
        super(DuplicateUploadsTestCase, cls).setUpClass()
        # This issue affects some 2.8 versions, but not 2.9.
        if (selectors.bug_is_untestable(1957, cls.cfg.version) and
                cls.cfg.version < Version('2.9')):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1957')
        unit = utils.http_get(DOCKER_IMAGE_URL)
        unit_type_id = 'docker_image'
        client = api.Client(cls.cfg, api.json_handler)
        repo_href = client.post(REPOSITORY_PATH, gen_repo())['_href']
        cls.resources.add(repo_href)
        cls.call_reports = tuple((
            utils.upload_import_unit(cls.cfg, unit, unit_type_id, repo_href)
            for _ in range(2)
        ))
