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
import unittest

from packaging.version import Version

from pulp_smash import api, selectors, utils
from pulp_smash.constants import PYTHON_EGG_URL, REPOSITORY_PATH
from pulp_smash.tests.python.api_v2.utils import gen_repo
from pulp_smash.tests.python.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class DuplicateUploadsTestCase(
        utils.BaseAPITestCase,
        utils.DuplicateUploadsMixin):
    """Test how well Pulp can deal with duplicate content unit uploads."""

    @classmethod
    def setUpClass(cls):
        """Create a Python repo. Upload a Python package into it twice."""
        super(DuplicateUploadsTestCase, cls).setUpClass()
        if (cls.cfg.version >= Version('2.11') and
                selectors.bug_is_untestable(2334, cls.cfg.version)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2334')
        unit = utils.http_get(PYTHON_EGG_URL)
        unit_type_id = 'python_package'
        client = api.Client(cls.cfg, api.json_handler)
        repo_href = client.post(REPOSITORY_PATH, gen_repo())['_href']
        cls.resources.add(repo_href)
        cls.upload_import_unit_args = (cls.cfg, unit, unit_type_id, repo_href)
