# coding=utf-8
"""Test Pulp's handling of no-op publishes.

As of version 2.9, Pulp has the ability to perform no-op publishes, instead of
the more typical full publish. A no-op publish is one in which no files are
changed, including metadata files. No-op publishes occur when all of the
components — including the repository, distributor and override config — are
unchanged.

Tests for this feature include the following:

* Publish a repository twice. (See :class:`PubTwiceTestCase`.)
* Publish a repository, change it, and publish it again. (See
  :class:`ChangeRepoTestCase`.)
* Publish a repository twice, with an override config the second time. (See
  :class:`pulp_smash.tests.rpm.api_v2.test_export.ExportDistributorTestCase`.)
* Publish a repository twice, with an override config both times. (See
  :class:`PubTwiceWithOverrideTestCase`.)

For more information, see:

* `Pulp #1724 <https://pulp.plan.io/issues/1724>`_
* `Pulp #1928 <https://pulp.plan.io/issues/1928>`_
* `Pulp Smash #127 <https://github.com/PulpQE/pulp-smash/issues/127>`_
* `Pulp Smash #232 <https://github.com/PulpQE/pulp-smash/issues/232>`_
"""
import inspect
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, exceptions, utils
from pulp_smash.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
    RPM_SIGNED_FEED_URL,
)
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import check_issue_2277
from pulp_smash.tests.rpm.utils import set_up_module


_REPO = {}
"""Information about the repository created by ``setUpModule``."""

_CLEANUP = []
"""A LIFO stack of clean-up actions to execute.

Each list element should be a tuple of ``(function, args, kwargs)``.
"""


def setUpModule():  # pylint:disable=invalid-name
    """Possibly skip the tests in this module. Create and sync an RPM repo.

    Skip this module of tests if Pulp is older than version 2.9. (See `Pulp
    #1724`_.) Then create an RPM repository with a feed and sync it. Test cases
    may copy data from this repository but should **not** change it.

    .. _Pulp #1724: https://pulp.plan.io/issues/1724
    """
    set_up_module()
    cfg = config.get_config()
    if cfg.version < Version('2.9'):
        raise unittest.SkipTest('This module requires Pulp 2.9 or greater.')
    if check_issue_2277(cfg):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2277')

    # Create and sync a repository.
    client = api.Client(cfg, api.json_handler)
    _CLEANUP.append((client.delete, [ORPHANS_PATH], {}))
    body = gen_repo()
    body['importer_config']['feed'] = RPM_SIGNED_FEED_URL
    _REPO.clear()
    _REPO.update(client.post(REPOSITORY_PATH, body))
    _CLEANUP.append((client.delete, [_REPO['_href']], {}))
    try:
        utils.sync_repo(cfg, _REPO)
    except (exceptions.CallReportError, exceptions.TaskReportError,
            exceptions.TaskTimedOutError):
        tearDownModule()
        raise


def tearDownModule():  # pylint:disable=invalid-name
    """Delete the repository created by :meth:`setUpModule`."""
    while _CLEANUP:
        action = _CLEANUP.pop()
        action[0](*action[1], **action[2])


def get_repomd_xml_path(distributor_rel_url):
    """Construct the path to a repository's ``repomd.xml`` file.

    :param distributor_rel_url: A distributor's ``relative_url`` option.
    :returns: An string path to a ``repomd.xml`` file.
    """
    return urljoin(
        urljoin('/pulp/repos/', distributor_rel_url),
        'repodata/repomd.xml',
    )


class BaseTestCase(utils.BaseAPITestCase):
    """Provide common behaviour for the test cases in this module."""

    @classmethod
    def setUpClass(cls):
        """Create a repository with a distributor, and populate it.

        In addition, create several variables for use by the test methods.
        """
        if inspect.getmro(cls)[0] == BaseTestCase:
            raise unittest.SkipTest('Abstract base class.')
        super(BaseTestCase, cls).setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        repo_href = client.post(REPOSITORY_PATH, gen_repo())['_href']
        cls.resources.add(repo_href)  # mark for deletion
        client.post(
            urljoin(repo_href, 'actions/associate/'),
            {'source_repo_id': _REPO['id']},
        )
        client.post(urljoin(repo_href, 'distributors/'), gen_distributor())

        # For use by sub-classes and test methods
        cls.repo = client.get(repo_href, params={'details': True})
        assert len(cls.repo['distributors']) == 1
        cls.call_reports = []  # dicts
        cls.repomd_xmls = []  # Response objects

    def test_first_publish(self):
        """Assert the first publish is a full publish."""
        call_report = self.call_reports[0]
        last_task = next(api.poll_spawned_tasks(self.cfg, call_report))
        self.assertIsInstance(last_task['result']['summary'], dict)


class NoOpPublishMixin(object):
    """Provide tests for the no-op publish test cases in this module."""

    def test_second_publish_tasks(self):
        """Assert the second publish's last task reports a no-op publish."""
        call_report = self.call_reports[1]
        last_task = next(api.poll_spawned_tasks(self.cfg, call_report))

        if hasattr(self, 'cfg') and self.cfg.version < Version('2.10'):
            summary = 'Skipped. Nothing changed since last publish'
        else:
            summary = (
                'Skipped: Repository content has not changed since last '
                'publish.'
            )
        self.assertEqual(
            last_task['result']['summary'],
            summary,
            last_task,
        )

    def test_second_publish_repomd(self):
        """Assert the two publishes produce identical ``repomd.xml`` files."""
        self.assertEqual(
            self.repomd_xmls[0].content,
            self.repomd_xmls[1].content,
        )


class PubTwiceTestCase(BaseTestCase, NoOpPublishMixin):
    """Publish a repository twice."""

    @classmethod
    def setUpClass(cls):
        """Publish a repository twice."""
        super(PubTwiceTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        distributor = cls.repo['distributors'][0]
        for _ in range(2):
            cls.call_reports.append(
                utils.publish_repo(cls.cfg, cls.repo).json()
            )
            cls.repomd_xmls.append(client.get(
                get_repomd_xml_path(distributor['config']['relative_url'])
            ))


class PubTwiceWithOverrideTestCase(BaseTestCase, NoOpPublishMixin):
    """Publish a repository twice, with an override config both times."""

    @classmethod
    def setUpClass(cls):
        """Publish a repository twice, with an override config both times."""
        super(PubTwiceWithOverrideTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        relative_url = utils.uuid4() + '/'
        for _ in range(2):
            cls.call_reports.append(utils.publish_repo(cls.cfg, cls.repo, {
                'id': cls.repo['distributors'][0]['id'],
                'override_config': {'relative_url': relative_url},
            }).json())
            cls.repomd_xmls.append(client.get(
                get_repomd_xml_path(relative_url)
            ))


class ChangeRepoTestCase(BaseTestCase):
    """Publish a repository, change it, and publish it again."""

    @classmethod
    def setUpClass(cls):
        """Publish a repository, change it, and publish it again."""
        super(ChangeRepoTestCase, cls).setUpClass()
        client = api.Client(cls.cfg)
        relative_url = cls.repo['distributors'][0]['config']['relative_url']

        # Publish, remove a unit, and publish again
        cls.call_reports.append(
            utils.publish_repo(cls.cfg, cls.repo).json()
        )
        cls.repomd_xmls.append(client.get(get_repomd_xml_path(relative_url)))
        client.post(
            urljoin(cls.repo['_href'], 'actions/unassociate/'),
            {'criteria': {'type_ids': ['rpm'], 'limit': 1}}
        )
        cls.call_reports.append(
            utils.publish_repo(cls.cfg, cls.repo).json()
        )
        cls.repomd_xmls.append(client.get(get_repomd_xml_path(relative_url)))

    def test_second_publish_tasks(self):
        """Assert the second publish's last task reports a no-op publish."""
        call_report = self.call_reports[1]
        last_task = next(api.poll_spawned_tasks(self.cfg, call_report))
        self.assertIsInstance(last_task['result']['summary'], dict, last_task)

    def test_second_publish_repomd(self):
        """Assert the two publishes produce identical ``repomd.xml`` files."""
        self.assertNotEqual(
            self.repomd_xmls[0].content,
            self.repomd_xmls[1].content,
        )
