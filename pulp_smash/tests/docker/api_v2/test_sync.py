# coding=utf-8
"""Tests that sync docker repositories."""
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_V1_FEED_URL,
    DOCKER_V2_FEED_URL,
    REPOSITORY_PATH,
)
from pulp_smash.tests.docker.api_v2.utils import gen_repo
from pulp_smash.tests.docker.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests on Pulp versions lower than 2.8."""
    set_up_module()
    if config.get_config().version < Version('2.8'):
        raise unittest.SkipTest('These tests require at least Pulp 2.8.')


class UpstreamNameTestsMixin(object):
    """Provides tests that sync a repository and override ``upstream_name``.

    Any class inheriting from this mixin must also inherit from
    :class:`pulp_smash.utils.BaseAPITestCase`.
    """

    def test_valid_upstream_name(self):
        """Sync the repository and pass a valid ``upstream_name``.

        Verify the sync succeeds.
        """
        api.Client(self.cfg).post(
            urljoin(self.repo_href, 'actions/sync/'),
            {'override_config': {'upstream_name': DOCKER_UPSTREAM_NAME}},
        )

    def test_invalid_upstream_name(self):
        """Sync the repository and pass an invalid ``upstream_name``.

        Verify the sync request is rejected with an HTTP 400 status code.
        """
        if selectors.bug_is_untestable(2230, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2230')
        docker_upstream_name = DOCKER_UPSTREAM_NAME.replace('/', ' ')
        response = api.Client(self.cfg, api.echo_handler).post(
            urljoin(self.repo_href, 'actions/sync/'),
            {'override_config': {'upstream_name': docker_upstream_name}},
        )
        self.assertEqual(response.status_code, 400)


class UpstreamNameV1TestCase(UpstreamNameTestsMixin, utils.BaseAPITestCase):
    """Sync a v1 docker repository with various ``upstream_name`` options.

    This test targets `Pulp #2230 <https://pulp.plan.io/issues/2230-docker>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create a docker repository with an importer.

        The importer has no ``upstream_name`` set. it must be passed via
        ``override_config`` when a sync is requested.
        """
        super(UpstreamNameV1TestCase, cls).setUpClass()
        body = gen_repo()
        body['importer_config'] = {
            'enable_v1': True,
            'feed': DOCKER_V1_FEED_URL,
        }
        cls.repo_href = (
            api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()['_href']
        )
        cls.resources.add(cls.repo_href)


class UpstreamNameV2TestCase(UpstreamNameTestsMixin, utils.BaseAPITestCase):
    """Sync a v2 docker repository with various ``upstream_name`` options.

    This test targets `Pulp #2230 <https://pulp.plan.io/issues/2230-docker>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create a docker repository with an importer.

        The importer has no ``upstream_name`` set. it must be passed via
        ``override_config`` when a sync is requested.
        """
        super(UpstreamNameV2TestCase, cls).setUpClass()
        body = gen_repo()
        body['importer_config'] = {'feed': DOCKER_V2_FEED_URL}
        cls.repo_href = (
            api.Client(cls.cfg).post(REPOSITORY_PATH, body).json()['_href']
        )
        cls.resources.add(cls.repo_href)
