# coding=utf-8
"""Test `Unassociating Content Units from a Repository`_ for RPM.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` and
:mod:`pulp_smash.tests.rpm.api_v2.test_sync_publish` hold true.

.. _Unassociating Content Units from a Repository:
   http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/content/associate.html#unassociating-content-units-from-a-repository
"""
import random
import time
import unittest
from urllib.parse import urljoin

from dateutil.parser import parse
from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM,
    RPM_UNSIGNED_FEED_COUNT,
    RPM_UNSIGNED_FEED_URL,
    RPM_UNSIGNED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import check_issue_2620
from pulp_smash.tests.rpm.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Maybe skip this module of tests."""
    set_up_module()
    if check_issue_2620(config.get_config()):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2620')


class RemoveUnitsTestCase(unittest.TestCase):
    """Remove units of various types from a synced RPM repository.

    At a high level, this test case does the following:

    1. Create and sync an RPM repository.
    2. For each of several different types of content, remove a content unit of
       that type from the repository.
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository."""
        cls.cfg = config.get_config()
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        cls.repo = client.post(REPOSITORY_PATH, body).json()
        try:
            utils.sync_repo(cls.cfg, cls.repo)
            cls.initial_units = utils.search_units(cls.cfg, cls.repo)
        except:
            cls.tearDownClass()
            raise
        cls.removed_units = []  # Units removed from the repository.

    @classmethod
    def tearDownClass(cls):
        """Remove the created repository and any orphans."""
        client = api.Client(cls.cfg)
        client.delete(cls.repo['_href'])
        client.delete(ORPHANS_PATH)

    def test_01_remove_units(self):
        """Remove several types of content units from the repository.

        Each removal is wrapped in a subTest. See :meth:`do_remove_unit`.
        """
        type_ids = ['erratum', 'package_category', 'package_group', 'rpm']
        random.shuffle(type_ids)
        for type_id in type_ids:
            with self.subTest(type_id=type_id):
                self.do_remove_unit(type_id)

    def test_02_remaining_units(self):
        """Assert the correct units are still in the repository.

        The repository should have all the units that were originally synced
        into the repository, minus those that have been removed.
        """
        removed_ids = {_get_unit_id(unit) for unit in self.removed_units}
        remaining_ids = {
            _get_unit_id(unit)
            for unit in utils.search_units(self.cfg, self.repo)
        }
        self.assertEqual(removed_ids & remaining_ids, set())

    def do_remove_unit(self, type_id):
        """Remove a content unit from the repository.

        Do the following:

        1. Note the repository's ``last_unit_removed`` field.
        2. Sleep for at least one second.
        3. Remove a unit of type ``type_id`` from the repository.
        4. Note the repository's ``last_unit_removed`` field.

        When the first unit is removed, assert that ``last_unit_removed``
        changes from null to a non-null value. When each subsequent unit is
        removed, assert that ``last_unit_removed`` increments.
        """
        lur_before = self.get_repo_last_unit_removed()
        time.sleep(1)  # ensure last_unit_removed increments
        unit = random.choice(_get_units_by_type(self.initial_units, type_id))
        self.removed_units.append(unit)
        _remove_unit(self.cfg, self.repo, unit)
        lur_after = self.get_repo_last_unit_removed()
        if len(self.removed_units) <= 1:
            self.assertIsNone(lur_before)
            self.assertIsNotNone(lur_after)
        else:
            self.assertGreater(parse(lur_after), parse(lur_before))

    def get_repo_last_unit_removed(self):
        """Get the repository's ``last_unit_removed`` attribute."""
        return (
            api
            .Client(self.cfg)
            .get(self.repo['_href'])
            .json()['last_unit_removed'])


class RepublishTestCase(utils.BaseAPITestCase):
    """Repeatedly publish a repository, with different content each time.

    Specifically, do the following:

    1. Create a repository.
    2. Add a content unit to the repository. Publish the repository.
    3. Unassociate the content unit and repository. Publish the repository.

    Verify that:

    * The ``last_unit_added``, ``last_unit_removed`` and ``last_publish``
      timestamps are correct.
    * The content unit in question is only available when associated with the
      repository.
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        cls.cfg = config.get_config()
        client = api.Client(cls.cfg)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        cls.repo = client.post(REPOSITORY_PATH, body).json()

    @classmethod
    def tearDownClass(cls):
        """Remove the created repository and any orphans."""
        client = api.Client(cls.cfg)
        client.delete(cls.repo['_href'])
        client.delete(ORPHANS_PATH)

    def test_01_add_unit(self):
        """Add a content unit to the repository. Publish the repository."""
        repo_before = self.get_repo()
        rpm = utils.http_get(RPM_UNSIGNED_URL)
        utils.upload_import_unit(
            self.cfg,
            rpm,
            {'unit_type_id': 'rpm'},
            self.repo,
        )
        utils.publish_repo(self.cfg, repo_before)
        repo_after = self.get_repo()
        with self.subTest(comment='last_unit_added'):
            if selectors.bug_is_untestable(1847, self.cfg.version):
                self.skipTest('https://pulp.plan.io/issues/1847')
            pre = repo_before['last_unit_added']
            post = repo_after['last_unit_added']
            self.assertIsNone(pre)
            self.assertIsNotNone(post)
        with self.subTest(comment='last_unit_removed'):
            pre = repo_before['last_unit_removed']
            post = repo_after['last_unit_removed']
            self.assertIsNone(pre)
            self.assertIsNone(post)
        with self.subTest(comment='last_publish'):
            pre = repo_before['distributors'][0]['last_publish']
            post = repo_after['distributors'][0]['last_publish']
            self.assertIsNone(pre)
            self.assertIsNotNone(post)

    def test_02_find_unit(self):
        """Search for the content unit. Assert it is available."""
        units = utils.search_units(self.cfg, self.repo, {'type_ids': ('rpm',)})
        self.assertEqual(len(units), 1, units)
        self.assertEqual(units[0]['metadata']['filename'], RPM)

    def test_03_unassociate_unit(self):
        """Unassociate the unit from the repository. Publish the repository."""
        repo_before = self.get_repo()
        units = utils.search_units(self.cfg, self.repo)
        self.assertEqual(len(units), 1, units)
        _remove_unit(self.cfg, self.repo, units[0])
        time.sleep(1)  # ensure last_publish increments
        utils.publish_repo(self.cfg, repo_before)
        repo_after = self.get_repo()
        with self.subTest(comment='last_unit_added'):
            if selectors.bug_is_untestable(1847, self.cfg.version):
                self.skipTest('https://pulp.plan.io/issues/1847')
            pre = parse(repo_before['last_unit_added'])
            post = parse(repo_after['last_unit_added'])
            self.assertEqual(pre, post)
        with self.subTest(comment='last_unit_removed'):
            pre = repo_before['last_unit_removed']
            post = repo_after['last_unit_removed']
            self.assertIsNone(pre)
            self.assertIsNotNone(post)
        with self.subTest(comment='last_publish'):
            pre = parse(repo_before['distributors'][0]['last_publish'])
            post = parse(repo_after['distributors'][0]['last_publish'])
            self.assertGreater(post, pre)

    def test_04_find_unit(self):
        """Search for the content unit. Assert it isn't available."""
        units = utils.search_units(self.cfg, self.repo, {'type_ids': ('rpm',)})
        self.assertEqual(len(units), 0, units)

    def get_repo(self):
        """Get detailed information about the repository."""
        return (
            api
            .Client(self.cfg)
            .get(self.repo['_href'], params={'details': True})
            .json())


def _get_unit_id(unit):
    """Return a unique identifier for the unit, depending on its type.

    It can be hard to uniquely identify a content unit. For example, whereas
    "erratum" content units have an "id" field, "rpm" content units do not.
    Based on the content type of the given content unit, this function returns
    — hopefully — the name and value of a unique identifier.
    """
    if unit['unit_type_id'] in ('package_langpacks', 'rpm'):
        key = '_id'
    else:
        key = 'id'
    return (key, unit['metadata'][key])


def _get_units_by_type(units, type_id):
    """Return a list of units having the given unit type ID."""
    return [unit for unit in units if unit['unit_type_id'] == type_id]


def _remove_unit(cfg, repo, unit):
    """Remove unit ``unit`` from repository ``repo``.

    Return the JSON-decoded response body.
    """
    path = urljoin(repo['_href'], 'actions/unassociate/')
    key, value = _get_unit_id(unit)
    body = {'criteria': {
        'filters': {'unit': {key: value}},
        'type_ids': [unit['unit_type_id']],
    }}
    return api.Client(cfg).post(path, body).json()


class SelectiveAssociateTestCase(utils.BaseAPITestCase):
    """Ensure Pulp only associate needed content.

    Test steps:

    1. Create and sync an RPM repository.
    2. Unassociate some RPMs from the repository created on the previous step.
    3. Sync the repository again and check if only the missing units were
       associated.

    See `Pulp #2457 <https://pulp.plan.io/issues/2457>`_
    """

    def test_all(self):
        """Check if Pulp only associate missing repo content."""
        if self.cfg.version < Version('2.11'):
            self.skipTest(
                'Selective association is available on Pulp 2.11+ see Pulp '
                '#2457 for more information'
            )
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        utils.sync_repo(self.cfg, repo)
        rpm_units = (
            _get_units_by_type(utils.search_units(self.cfg, repo), 'rpm')
        )
        # Let's select up to 1/5 of the available units to remove
        to_remove = random.sample(
            rpm_units, random.randrange(int(RPM_UNSIGNED_FEED_COUNT / 4)))
        for unit in to_remove:
            _remove_unit(self.cfg, repo, unit)
        report = client.post(urljoin(repo['_href'], 'actions/sync/'))
        tasks = tuple(api.poll_spawned_tasks(self.cfg, report))
        self.assertEqual(len(tasks), 1, tasks)
        self.assertEqual(
            tasks[0]['result']['added_count'], len(to_remove), to_remove)
