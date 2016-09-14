# coding=utf-8
"""Test Pulp's handling of `orphaned content units`_.

This module integrates tightly with `Pulp Fixtures`_. `Pulp Smash #134`_
describes specific tests that should be in this module.

.. _Pulp Fixtures: https://github.com/PulpQE/pulp-fixtures
.. _Pulp Smash #134: https://github.com/PulpQE/pulp-smash/issues/134
.. _orphaned content units:
    http://docs.pulpproject.org/en/latest/user-guide/admin-client/orphan.html
"""
import random
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, utils
from pulp_smash.constants import ORPHANS_PATH, REPOSITORY_PATH, RPM_FEED_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _count_orphans(orphans):
    """Count the total number of orphans across all content types."""
    return sum(content_type['count'] for content_type in orphans.values())


class OrphansTestCase(utils.BaseAPITestCase):
    """Establish that API calls related to orphans function correctly.

    At a high level, this test case does the following:

    1. Create an RPM repository with a feed and sync in content. Delete the
       repository, thus leaving behind orphans.
    2. Make an API call related to orphans, and assert that the call had the
       desired effect. Repeat as needed.

    .. NOTE:: Though the test_* methods must execute in a specific order, they
        (should) all function correctly no matter how many other test_* methods
        fail.
    """

    @classmethod
    def setUpClass(cls):
        """Create, sync and delete an RPM repository.

        Doing this provides orphans that the remaining test methods can make
        use of. If this method fails, it's possible that other repositories
        exist with references to the same content units.
        """
        super(OrphansTestCase, cls).setUpClass()

        # Create orphans.
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        try:
            utils.sync_repo(cls.cfg, repo['_href'])
        finally:
            client.delete(repo['_href'])

        # Verify that orphans are present. Support for langpack content units
        # was added in Pulp 2.9.
        orphans = client.get(ORPHANS_PATH)
        expected_count = 39
        if cls.cfg.version >= Version('2.9'):
            expected_count += 1
        actual_count = _count_orphans(orphans)
        if expected_count != actual_count:
            # We can't use fail(), as it's an instance method.
            raise AssertionError(
                'Test case setup failed. We attempted to create {} orphans, '
                'but actually created {}. Orphans: {}'
                .format(expected_count, actual_count, orphans)
            )

    def check_one_orphan_deleted(self, orphans_pre, orphans_post, orphan):
        """Ensure that a specific orphan is well and truly deleted.

        :param orphans_pre: The response to GET
            :data:`pulp_smash.constants.ORPHANS_PATH` before the orphan was
            deleted.
        :param orphans_post: The response to GET
            :data:`pulp_smash.constants.ORPHANS_PATH` after the orphan was
            deleted.
        :param orphan: A dict describing the orphan that was deleted.
        :returns: Nothing.
        """
        with self.subTest(comment='verify total count'):
            self.assertEqual(
                _count_orphans(orphans_pre) - 1,
                _count_orphans(orphans_post),
                orphan,
            )
        with self.subTest(comment='verify erratum count'):
            self.assertEqual(
                orphans_pre['erratum']['count'] - 1,
                orphans_post['erratum']['count'],
                orphan,
            )
        response = api.Client(self.cfg, api.echo_handler).get(orphan['_href'])
        with self.subTest(comment='verify erratum is unavailable'):
            self.assertEqual(response.status_code, 404)

    def test_01_get_by_href(self):
        """Get an orphan by its href."""
        client = api.Client(self.cfg)
        orphans = client.get(urljoin(ORPHANS_PATH, 'erratum/')).json()
        orphan = random.choice(orphans)
        response = client.get(orphan['_href'])
        with self.subTest(comment='verify status code'):
            self.assertEqual(response.status_code, 200)
        with self.subTest(comment='verify href'):
            self.assertEqual(orphan['_href'], response.json()['_href'])

    def test_01_get_by_invalid_type(self):
        """Get orphans by content type. Specify a non-existent content type."""
        client = api.Client(self.cfg, api.echo_handler)
        response = client.get(urljoin(ORPHANS_PATH, 'foo/'))
        self.assertEqual(response.status_code, 404)

    def test_02_delete_by_href(self):
        """Delete an orphan by its href."""
        client = api.Client(self.cfg, api.json_handler)
        orphans_pre = client.get(ORPHANS_PATH)
        orphan = random.choice(client.get(urljoin(ORPHANS_PATH, 'erratum/')))
        client.delete(orphan['_href'])
        orphans_post = client.get(ORPHANS_PATH)
        self.check_one_orphan_deleted(orphans_pre, orphans_post, orphan)

    def test_02_delete_by_type_and_id(self):
        """Delete an orphan by its ID and type.

        This test exercises `Pulp #1923 <https://pulp.plan.io/issues/1923>`_.
        """
        client = api.Client(self.cfg, api.json_handler)
        orphans_pre = client.get(ORPHANS_PATH)
        orphan = random.choice(client.get(urljoin(ORPHANS_PATH, 'erratum/')))
        client.post('pulp/api/v2/content/actions/delete_orphans/', [{
            'content_type_id': 'erratum',
            'unit_id': orphan['_id'],
        }])
        orphans_post = client.get(ORPHANS_PATH)
        self.check_one_orphan_deleted(orphans_pre, orphans_post, orphan)

    def test_03_delete_by_content_type(self):
        """Delete orphans by their content type."""
        client = api.Client(self.cfg, api.json_handler)
        orphans_pre = client.get(ORPHANS_PATH)
        client.delete(urljoin(ORPHANS_PATH, 'erratum/'))
        orphans_post = client.get(ORPHANS_PATH)
        with self.subTest(comment='verify total count'):
            self.assertEqual(
                _count_orphans(orphans_pre) - orphans_pre['erratum']['count'],
                _count_orphans(orphans_post),
                orphans_post,
            )
        with self.subTest(comment='verify erratum count'):
            self.assertEqual(orphans_post['erratum']['count'], 0, orphans_post)

    def test_04_delete_all(self):
        """Delete all orphans."""
        client = api.Client(self.cfg, api.json_handler)
        client.delete(ORPHANS_PATH)
        orphans = client.get(ORPHANS_PATH)
        self.assertEqual(_count_orphans(orphans), 0, orphans)
