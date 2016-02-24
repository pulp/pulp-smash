# coding utf-8
"""Test the functionality in RPM repos when `retain_old_count`_ is specified.

Following steps are executed in order to test correct functionality
of repository created with valid feed and retain_old_count option set.

1. Create repository foo with valid feed, run sync, add distributor to it
   and publish over http and https.
2. Create second repository bar, with feed pointing to first repository,
   set retain_old_count=0 and run sync.
3. Assert that repositories do not contain same set of units.
4. Assert that number or RPMs in repo bar is less then in foo repo.

.. _retain_old_count:
    https://pulp-rpm.readthedocs.org/en/latest/tech-reference/yum-plugins.html
"""

from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401


from pulp_smash import api, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM_FEED_URL,
)

_PUBLISH_DIR = 'pulp/repos/'


def _gen_repo():
    """Return a semi-random dict for use in creating an RPM repostirory."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'yum_importer',
        'notes': {'_repo-type': 'rpm-repo'},
    }


def _gen_distributor():
    """Return a semi-random dict for use in creating a YUM distributor."""
    return {
        'auto_publish': False,
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'yum_distributor',
        'distributor_config': {
            'http': True,
            'https': True,
            'relative_url': utils.uuid4() + '/',
        },
    }


class RetainOldCountTestCase(utils.BaseAPITestCase):
    """Test functionality of --retain-old-count option specified."""

    @classmethod
    def setUpClass(cls):  # pylint:disable=arguments-differ
        """Create two repositories, first is feed of second one.

        Provides server config and set of iterable to delete.
        Following steps are executed:
            1. Create repository foo with feed, sync and publish it.
            2. Create repository bar with foo as a feed with retain-old-count=0
            3. Run sync of repo foo.
            3. Get information on both repositories.
        """
        super(RetainOldCountTestCase, cls).setUpClass()

        cls.responses = {}
        client = api.Client(cls.cfg, api.safe_handler)

        bodies = tuple((_gen_repo() for _ in range(2)))
        # repo with feed from remote source
        bodies[0]['importer_config']['feed'] = RPM_FEED_URL
        repos = []
        repos.append(client.post(REPOSITORY_PATH, bodies[0]).json())
        sync_path = urljoin(repos[0]['_href'], 'actions/sync/')
        # Run sync and wait for the task to complete
        cls.responses['sync'] = []
        cls.responses['sync'].append(client.post(
            sync_path, {'override_config': {}}
        ))
        # Add distributor and publish
        cls.responses['distribute'] = client.post(
            urljoin(repos[0]['_href'], 'distributors/'),
            _gen_distributor(),
        )
        cls.responses['publish'] = [client.post(
            urljoin(repos[0]['_href'], 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )]
        # Use http feed instead of https to avoid possible config problems
        # Repo with feed from 1st repo
        bodies[1]['importer_config']['feed'] = urljoin(
            # Create http url from base_url
            cls.cfg.base_url,
            _PUBLISH_DIR +
            cls.responses['distribute'].json()['config']['relative_url'],
        )
        # set retain_old_count
        bodies[1]['importer_config']['retain_old_count'] = 0
        # Turning off validation is neccessary, as each https feed requires
        # certificate to be specified
        bodies[1]['importer_config']['ssl_validation'] = False
        # Create and sync second repo
        repos.append(client.post(REPOSITORY_PATH, bodies[1]).json())
        sync_path = urljoin(repos[1]['_href'], 'actions/sync/')
        cls.responses['sync'].append(client.post(
            sync_path, {'override_config': {}}
        ))

        cls.repos = [client.get(repo['_href']).json() for repo in repos]

    def test_status_code(self):
        """Verify th HTTP status code of each server response."""
        for step, code in (
                ('sync', 202),
                ('publish', 202),
        ):
            with self.subTest(step=step):
                for response in self.responses[step]:
                    self.assertEqual(response.status_code, code)
        for step, code in (
                ('distribute', 201),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)

    def test_retain_old_count_works(self):
        """Test that content_units_counts in repositories differ.

        Test that second repo has less rpm units than first repo due to
        retain_old_count option value set.
        """
        counts = [repo.get('content_unit_counts', {}) for repo in self.repos]
        self.assertNotEqual(counts[0], counts[1])
        # remote source has 2 versions of walrus rpm
        self.assertEqual(counts[1]['rpm'], 31)
