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
from pulp_smash import api, utils
from pulp_smash.constants import PUPPET_MODULE_URL_1, REPOSITORY_PATH
from pulp_smash.tests.puppet.api_v2.utils import gen_repo
from pulp_smash.tests.puppet.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class DuplicateUploadsTestCase(
        utils.BaseAPITestCase,
        utils.DuplicateUploadsMixin):
    """Test how well Pulp can deal with duplicate content unit uploads."""

    @classmethod
    def setUpClass(cls):
        """Create a Puppet repository."""
        super(DuplicateUploadsTestCase, cls).setUpClass()
        unit = utils.http_get(PUPPET_MODULE_URL_1)
        import_params = {'unit_type_id': 'puppet_module'}
        repo = api.Client(cls.cfg).post(REPOSITORY_PATH, gen_repo()).json()
        cls.upload_import_unit_args = (cls.cfg, unit, import_params, repo)
        cls.resources.add(repo['_href'])
