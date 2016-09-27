# coding utf-8
"""Test the functionality in RPM repos when `retain_old_count`_ is specified.

Following steps are executed in order to test correct functionality of
repository created with valid feed and `retain_old_count`_ option set.

1. Create repository foo with valid feed, run sync, add distributor to it and
   publish over http and https.
2. Create second repository bar, with feed pointing to first repository, set
   ``retain_old_count=0`` and run sync.
3. Assert that repositories do not contain same set of units.
4. Assert that number or RPMs in repo bar is less then in foo repo.

.. _retain_old_count:
    https://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, selectors, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import

_PUBLISH_DIR = 'pulp/repos/'


class RetainOldCountTestCase(utils.BaseAPITestCase):
    """Test functionality of --retain-old-count option specified."""

    @classmethod
    def setUpClass(cls):  # pylint:disable=arguments-differ
        """Create two repositories, first is feed of second one.

        Provides server config and set of iterable to delete. Following steps
        are executed:

        1. Create repository foo with feed, sync and publish it.
        2. Create repository bar with foo as a feed with
           ``retain_old_count=0``.
        3. Run sync of repo foo.
        4. Get information on both repositories.
        """
        super(RetainOldCountTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(2277, cls.cfg.version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        client = api.Client(cls.cfg)
        cls.responses = {}
        hrefs = []  # repository hrefs

        # Create and sync the first repository.
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        hrefs.append(client.post(REPOSITORY_PATH, body).json()['_href'])
        cls.responses['first sync'] = utils.sync_repo(cls.cfg, hrefs[0])

        # Add distributor and publish
        cls.responses['distribute'] = client.post(
            urljoin(hrefs[0], 'distributors/'),
            gen_distributor(),
        )
        cls.responses['publish'] = client.post(
            urljoin(hrefs[0], 'actions/publish/'),
            {'id': cls.responses['distribute'].json()['id']},
        )

        # Create and sync the second repository. Ensure it fetches content from
        # the first, and that the `retain_old_count` option is set correctly.
        # We disable SSL validation for a practical reason: each HTTPS feed
        # must have a certificate to work, which is burdensome to do here.
        body = gen_repo()
        body['importer_config']['feed'] = urljoin(
            cls.cfg.base_url,
            _PUBLISH_DIR +
            cls.responses['distribute'].json()['config']['relative_url'],
        )
        body['importer_config']['retain_old_count'] = 0  # see docstring
        body['importer_config']['ssl_validation'] = False
        hrefs.append(client.post(REPOSITORY_PATH, body).json()['_href'])
        cls.responses['second sync'] = utils.sync_repo(cls.cfg, hrefs[1])

        # Read the repositories and mark them for deletion.
        cls.repos = [client.get(href).json() for href in hrefs]
        cls.resources.update(set(hrefs))

    def test_status_code(self):
        """Verify the HTTP status code of each server response."""
        for step, code in (
                ('first sync', 202),
                ('distribute', 201),
                ('publish', 202),
                ('second sync', 202),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)

    def test_retain_old_count_works(self):
        """Test that ``content_unit_counts`` in repositories differ.

        Most of the RPMs in the first repository are unique. However, there are
        two different versions of the "walrus" RPM. When we copy its contents
        to the second repository with ``retain_old_count=0``, zero old versions
        of the "walrus" RPM will be copied.
        """
        counts = [repo.get('content_unit_counts', {}) for repo in self.repos]
        self.assertEqual(counts[0]['rpm'] - 1, counts[1]['rpm'])
