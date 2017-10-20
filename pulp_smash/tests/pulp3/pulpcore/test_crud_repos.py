# coding=utf-8
"""Tests that CRUD repositories."""
import unittest
from urllib.parse import urljoin, urlsplit

from pulp_smash import api, config, utils
from pulp_smash.tests.pulp3.constants import REPO_PATH
from pulp_smash.tests.pulp3.pulpcore.utils import gen_repo
from pulp_smash.tests.pulp3.utils import adjust_url, get_auth, get_base_url
from pulp_smash.tests.pulp3.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class CRUDRepoTestCase(unittest.TestCase):
    """Tests that CRUD minimal repositories."""

    @classmethod
    def setUpClass(cls):
        """Create config variables."""
        cls.auth = get_auth()
        cls.cfg = config.get_config()
        cls.url = adjust_url(get_base_url())
        cls.repos = []
        cls._href = []

    def test_create_repo(self):
        """Create repository using a given auth method.."""
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        repo = client.post(REPO_PATH, gen_repo(), auth=self.auth)
        self.repos.append(repo)
        self._href.append(repo['_href'])

    def test_read_repo(self):
        """Read a specific repository."""
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        client.get(REPO_PATH, params={'name': self.repos[0]['name']})

    def test_read_all_repos(self):
        """Read all repositories."""
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url
        client.get(REPO_PATH)

    def test_update_repo(self):
        """Update repository using a given auth method."""
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['url'] = self.url

        with self.subTest('Partial Update'):
            client.response_handler = api.echo_handler
            client.patch(
                urljoin(REPO_PATH, self.repos[0]['name'] + '/'),
                {'description': utils.uuid4()},
                auth=self.auth
            )

        with self.subTest('Full Update'):
            repo_href = client.put(
                urljoin(REPO_PATH, self.repos[0]['name'] + '/'),
                gen_repo(),
                auth=self.auth
            ).json()
            self._href.pop(0)
            self._href.append((urlsplit(repo_href[0]['_href']))[2])

    def test_delete_repo(self):
        """Delete a repository using a given auth method."""
        client = api.Client(self.cfg, api.echo_handler)
        client.request_kwargs['url'] = self.url
        for _href in self._href:
            client.delete(
                REPO_PATH,
                params={'name': get_repo_name(_href)},
                auth=self.auth
            )


def get_repo_name(href):
    """Return the name of certain repository.

    Given that ``_href`` was provided.
    """
    return href.split('/')[-1]
