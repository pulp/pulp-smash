# coding=utf-8
"""Tests that sync docker repositories."""
import unittest
from urllib.parse import urljoin

from packaging.version import Version
from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors
from pulp_smash.constants import DOCKER_V1_FEED_URL, DOCKER_V2_FEED_URL
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.tests.pulp2.docker.api_v2.utils import gen_repo
from pulp_smash.tests.pulp2.docker.utils import (
    get_upstream_name,
    set_up_module,
)


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests on Pulp versions lower than 2.8."""
    set_up_module()
    if config.get_config().pulp_version < Version('2.8'):
        raise unittest.SkipTest('These tests require at least Pulp 2.8.')


class UpstreamNameTestCase(unittest.TestCase):
    """Sync v1 and Docker repositories with varying ``upstream_name``."""

    @classmethod
    def setUpClass(cls):
        """Create shared variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_v1_valid_upstream_name(self):
        """Sync a v1 Docker repository with a valid ``upstream_name``.

        Do the following:

        1. Create a v1 Docker repository.
        2. Sync the repository with a valid upstream name, and assert it
           succeeds.

        In addition, verify its ``last_override_config`` attribute is an empty
        dict after each step.
        """
        repo = self._do_create_v1_repo()
        self._do_test_last_override_config(repo)
        self._do_test_valid_upstream_name(repo)
        self._do_test_last_override_config(repo)

    def test_v1_invalid_upstream_name(self):
        """Sync a v1 Docker repository with a invalid ``upstream_name``.

        Do the following:

        1. Create a v1 Docker repository.
        2. Sync the repository with an invalid upstream name, and assert it
           succeeds.

        In addition, verify its ``last_override_config`` attribute is an empty
        dict after each step.
        """
        repo = self._do_create_v1_repo()
        self._do_test_last_override_config(repo)
        self._do_test_invalid_upstream_name(repo)
        self._do_test_last_override_config(repo)

    def test_v2_valid_upstream_name(self):
        """Sync a v2 Docker repository with a valid ``upstream_name``.

        Do the same as :meth:`test_v1_valid_upstream_name`, but with a v2
        repository.
        """
        repo = self._do_create_v2_repo()
        self._do_test_last_override_config(repo)
        self._do_test_valid_upstream_name(repo)
        self._do_test_last_override_config(repo)

    def test_v2_invalid_upstream_name(self):
        """Sync a v2 Docker repository with a invalid ``upstream_name``.

        Do the same as :meth:`test_v1_invalid_upstream_name`, but with a v2
        repository.
        """
        repo = self._do_create_v2_repo()
        self._do_test_last_override_config(repo)
        self._do_test_invalid_upstream_name(repo)
        self._do_test_last_override_config(repo)

    def _do_create_v1_repo(self):
        """Create a v1 Docker repository, and schedule it for deletion.

        The repository's importer has no ``upstream_name`` set. One must be
        passed via an ``override_config`` when a sync is requested.
        """
        repo = self.client.post(
            REPOSITORY_PATH,
            gen_repo(importer_config={
                'enable_v1': True,
                'enable_v2': False,
                'feed': DOCKER_V1_FEED_URL,
            })
        )
        self.addCleanup(self.client.delete, repo['_href'])
        return repo

    def _do_create_v2_repo(self):
        """Create a v2 Docker repository, and schedule it for deletion.

        The repository's importer has no ``upstream_name`` set. One must be
        passed via an ``override_config`` when a sync is requested.
        """
        repo = self.client.post(
            REPOSITORY_PATH,
            gen_repo(importer_config={'feed': DOCKER_V2_FEED_URL}),
        )
        self.addCleanup(self.client.delete, repo['_href'])
        return repo

    def _do_test_last_override_config(self, repo):
        """Assert ``last_override_config`` is empty.

        This method tests `Pulp #3521 <https://pulp.plan.io/issues/3521>`_.
        """
        if not selectors.bug_is_fixed(3521, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3521')
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(repo['importers'][0]['last_override_config'], {})

    def _do_test_valid_upstream_name(self, repo):
        """Sync a v1 Docker repository with a valid ``upstream_name``."""
        self.client.post(
            urljoin(repo['_href'], 'actions/sync/'),
            {'override_config': {'upstream_name': get_upstream_name(self.cfg)}}
        )

    def _do_test_invalid_upstream_name(self, repo):
        """Sync a v2 Docker repository with an invalid ``upstream_name``.

        This method tests `Pulp #2230 <https://pulp.plan.io/issues/2230>`_.
        """
        if not selectors.bug_is_fixed(2230, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2230')
        with self.assertRaises(HTTPError):
            self.client.post(
                urljoin(repo['_href'], 'actions/sync/'),
                {'override_config': {
                    'upstream_name':
                    get_upstream_name(self.cfg).replace('/', ' ')
                }},
            )
