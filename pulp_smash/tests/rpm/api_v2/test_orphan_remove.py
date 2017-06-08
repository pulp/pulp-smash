# coding=utf-8
"""Test Pulp's handling of `orphaned content units`_.

This module integrates tightly with `Pulp Fixtures`_. `Pulp Smash #134`_ and
`Pulp Smash #459` describe specific tests that should be in this module.

.. _Pulp Fixtures: https://github.com/PulpQE/pulp-fixtures
.. _Pulp Smash #134: https://github.com/PulpQE/pulp-smash/issues/134
.. _Pulp Smash #459: https://github.com/PulpQE/pulp-smash/issues/459
.. _orphaned content units:
    http://docs.pulpproject.org/en/latest/user-guide/admin-client/orphan.html
"""
import random
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM_SIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _count_orphans(orphans):
    """Count the total number of orphans across all content types."""
    return sum(content_type['count'] for content_type in orphans.values())


class OrphansTestCase(unittest.TestCase):
    """Establish that API calls related to orphans function correctly.

    At a high level, this test case does the following:

    1. Create an RPM repository and populate it with content. Delete the
       repository, thus leaving behind orphans.
    2. Make several orphan-related API calls, and assert that each call has the
       desired effect.
    """

    @classmethod
    def setUpClass(cls):
        """Create orphans.

        Create, sync and delete an RPM repository. Doing this creates orphans
        that the test methods can make use of.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        try:
            utils.sync_repo(cfg, repo)
        finally:
            client.delete(repo['_href'])
        cls.orphans_available = False

    def test_00_orphans_available(self):
        """Assert that an expected number of orphans is present.

        If the expected number of orphans is present, set a class variable
        indicating such. The following test methods can conditionally run or
        skip based on this variable. If this method fails, it may indicate that
        other repositories exist and have references to the same content units.
        """
        orphans = api.Client(config.get_config()).get(ORPHANS_PATH).json()
        actual_count = _count_orphans(orphans)
        # Support for langpack content units was added in Pulp 2.9.
        expected_count = 39
        if config.get_config().version >= Version('2.9'):
            expected_count += 1
        self.assertEqual(actual_count, expected_count, orphans)
        type(self).orphans_available = True

    @selectors.skip_if(bool, 'orphans_available', False)
    def test_01_get_by_href(self):
        """Get an orphan by its href."""
        client = api.Client(config.get_config())
        orphans = client.get(urljoin(ORPHANS_PATH, 'erratum/')).json()
        orphan = random.choice(orphans)
        response = client.get(orphan['_href'])
        with self.subTest(comment='verify status code'):
            self.assertEqual(response.status_code, 200)
        with self.subTest(comment='verify href'):
            self.assertEqual(orphan['_href'], response.json()['_href'])

    @selectors.skip_if(bool, 'orphans_available', False)
    def test_01_get_by_invalid_type(self):
        """Get orphans by content type. Specify a non-existent content type."""
        client = api.Client(config.get_config(), api.echo_handler)
        response = client.get(urljoin(ORPHANS_PATH, 'foo/'))
        self.assertEqual(response.status_code, 404)

    @selectors.skip_if(bool, 'orphans_available', False)
    def test_02_delete_by_href(self):
        """Delete an orphan by its href."""
        client = api.Client(config.get_config(), api.json_handler)
        orphans_pre = client.get(ORPHANS_PATH)
        orphan = random.choice(client.get(urljoin(ORPHANS_PATH, 'erratum/')))
        client.delete(orphan['_href'])
        orphans_post = client.get(ORPHANS_PATH)
        self.check_one_orphan_deleted(orphans_pre, orphans_post, orphan)

    @selectors.skip_if(bool, 'orphans_available', False)
    def test_02_delete_by_type_and_id(self):
        """Delete an orphan by its ID and type.

        This test exercises `Pulp #1923 <https://pulp.plan.io/issues/1923>`_.
        """
        client = api.Client(config.get_config(), api.json_handler)
        orphans_pre = client.get(ORPHANS_PATH)
        orphan = random.choice(client.get(urljoin(ORPHANS_PATH, 'erratum/')))
        client.post('pulp/api/v2/content/actions/delete_orphans/', [{
            'content_type_id': 'erratum',
            'unit_id': orphan['_id'],
        }])
        orphans_post = client.get(ORPHANS_PATH)
        self.check_one_orphan_deleted(orphans_pre, orphans_post, orphan)

    @selectors.skip_if(bool, 'orphans_available', False)
    def test_03_delete_by_content_type(self):
        """Delete orphans by their content type."""
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        orphans_pre = client.get(ORPHANS_PATH)
        call_report = client.delete(urljoin(ORPHANS_PATH, 'erratum/'))
        orphans_post = client.get(ORPHANS_PATH)
        with self.subTest(comment='verify "result" field'):
            if selectors.bug_is_untestable(1268, cfg.version):
                self.skipTest('https://pulp.plan.io/issues/1268')
            task = tuple(api.poll_spawned_tasks(cfg, call_report))[-1]
            self.assertIsInstance(task['result'], int)
            self.assertGreater(task['result'], 0)
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
        cfg = config.get_config()
        call_report = api.Client(cfg).delete(ORPHANS_PATH).json()
        if selectors.bug_is_untestable(1268, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1268')
        task = tuple(api.poll_spawned_tasks(cfg, call_report))[-1]
        self.assertIsInstance(task['result'], dict)
        self.assertGreater(sum(task['result'].values()), 0)

    def test_05_no_orphans_exist(self):
        """Assert no orphans exist."""
        orphans = api.Client(config.get_config()).get(ORPHANS_PATH).json()
        self.assertEqual(_count_orphans(orphans), 0, orphans)

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
        response = api.Client(
            config.get_config(),
            api.echo_handler
        ).get(orphan['_href'])
        with self.subTest(comment='verify erratum is unavailable'):
            self.assertEqual(response.status_code, 404)
