# coding=utf-8
"""Tests that sync repositories whose packages are in varying locations.

The packages in a repository may be in the root of a repository, like so::

    repository
    ├── bear-4.1-1.noarch.rpm
    ├── camel-0.1-1.noarch.rpm
    ├── …
    └── repodata
        ├── b83f17e552fa7a86f75811147251b4cc4f411eacfde5a187375d-primary.xml.gz
        ├── 5ec9512bc0461c579aebd3fe6d89133db5255cc1e15d529a20-other.sqlite.bz2
        └── …

However, the files in the `repodata/` directory specify the paths to each file
included in a repository. Consequently, other layouts are possible, like so::

    repository
    ├── packages
    │   └── keep-going
    │       ├── bear-4.1-1.noarch.rpm
    │       ├── camel-0.1-1.noarch.rpm
    │       └── …
    └── repodata
        ├── b83f17e552fa7a86f75811147251b4cc4f411eacfde5a187375d-primary.xml.gz
        ├── 5ec9512bc0461c579aebd3fe6d89133db5255cc1e15d529a20-other.sqlite.bz2
        └── …

The tests in this module verify that Pulp can correctly handle these
situations.
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM,
    RPM_ALT_LAYOUT_FEED_URL,
    RPM_UNSIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import check_issue_2354
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def publish_repo(cfg, repo, distributor_id=None):
    """Publish a repository.

    :param pulp_smash.config.ServerConfig cfg: Information about the Pulp host.
    :param repo: A dict of detailed information about the repository to be
        published.
    :param distributor_id: The ID of the distributor to publish. If not
        specified, the distributor described in the ``repo`` dict is used.
    :raises: ``ValueError`` when ``distributor_id`` is not passed, and ``repo``
        does not have exactly one distributor.
    :returns: The decoded body of the server's reponse. (A call report.)
    """
    if distributor_id is None:
        if len(repo['distributors']) != 1:
            raise ValueError(
                'No distributor ID was passed, and the given repository does '
                'not have exactly one distributor. Repository distributors: {}'
                .format(repo['distributors'])
            )
        distributor_id = repo['distributors'][0]['id']
    return api.Client(cfg).post(
        urljoin(repo['_href'], 'actions/publish/'),
        {'id': distributor_id},
    )


def get_unit(cfg, unit_name, repo, distributor_id=None):
    """Download a file from a published repository.

    :param pulp_smash.config.ServerConfig cfg: Information about the Pulp host.
    :param unit_name: The name of the content unit in the published repository.
    :param repo: A dict of detailed information about the repository.
    :param distributor_id: The ID of the distributor used to publish the
        content unit. If not passed, the distributor described in the ``repo``
        dict is used.
    :raises: ``ValueError`` when ``distributor_id`` is not passed, and ``repo``
        does not have exactly one distributor.
    :returns: The raw response. The fetched unit is available as
        ``response.content``.
    """
    if distributor_id is None:
        if len(repo['distributors']) != 1:
            raise ValueError(
                'No distributor ID was passed, and the given repository does '
                'not have exactly one distributor. Repository distributors: {}'
                .format(repo['distributors'])
            )
        distributor_id = repo['distributors'][0]['id']
    path = urljoin(
        '/pulp/repos/',
        repo['distributors'][0]['config']['relative_url'] + '/',
    )
    path = urljoin(path, unit_name)
    return api.Client(cfg).get(path)


class ReuseContentTestCase(unittest.TestCase):
    """Sync two repositories with identical content but differing layouts.

    If two repositories have some identical content, then Pulp should be
    able to re-use that content. This is true even if the content is placed in
    differing locations in the two repositories. Do the following:

    1. Create a pair of repositories. Give the two repositories a download
       policy of either on demand or background. (One of these download
       policies must be used to ensure that the Pulp streamer is used.) Give
       the two repositories differing feeds, where the feeds reference a pair
       of repositories with some identical content and differing layouts.
    2. Sync each of the repositories.
    3. Publish each of the repositories.
    4. Fetch an identical content unit from each of the two repositories.

    This test targets `Pulp #2354`_.

    .. _Pulp #2354: https://pulp.plan.io/issues/2354
    """

    def test_all(self):
        """Sync two repositories w/identical content but differing layouts."""
        cfg = config.get_config()
        if check_issue_2354(cfg):
            self.skipTest('https://pulp.plan.io/issues/2354')
        client = api.Client(cfg, api.json_handler)

        repos = [
            self.create_repo(cfg, feed, 'on_demand')
            for feed in (RPM_ALT_LAYOUT_FEED_URL, RPM_UNSIGNED_FEED_URL)
        ]
        for repo in repos:
            utils.sync_repo(cfg, repo['_href'])

        repos = [
            client.get(repo['_href'], params={'details': True})
            for repo in repos
        ]
        for repo in repos:
            publish_repo(cfg, repo)

        repos = [
            client.get(repo['_href'], params={'details': True})
            for repo in repos
        ]
        rpms = []
        for repo in repos:
            with self.subTest(repo=repo):
                rpms.append(get_unit(cfg, RPM, repo).content)
        self.assertEqual(len(rpms), len(repos))
        self.assertEqual(rpms[0], rpms[1], repos)

    def create_repo(self, cfg, feed, download_policy):
        """Create an RPM repository with the given feed and download policy.

        Also, schedule the repository for deletion at the end of the current
        test. Return a detailed dict of information about the just-created
        repository.
        """
        client = api.Client(cfg)
        body = gen_repo()
        body['importer_config']['feed'] = feed
        body['importer_config']['download_policy'] = download_policy
        distributor = gen_distributor()
        distributor['distributor_config']['relative_url'] = body['id']
        body['distributors'] = [distributor]
        repo = client.post(REPOSITORY_PATH, body).json()
        self.addCleanup(client.delete, repo['_href'])
        return repo
