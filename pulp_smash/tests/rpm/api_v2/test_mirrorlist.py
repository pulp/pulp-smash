# coding=utf-8
"""Tests that exercise Pulp's support for mirrorlist feeds.

The tests in this module target:

* `Pulp #175 <https://pulp.plan.io/issues/175>`_: "As a user, I can specify
  mirrorlists for rpm repository feeds."
* `Pulp #2224 <https://pulp.plan.io/issues/2224>`_: "Cannot sync from
  mirrorlists."

The test cases in this module reference "good," "mixed" and "bad" mirrorlist
files. A "good" file contains only valid references, a "mixed" file contains
both valid and invalid references, and a "bad" file contains only invalid
references.
"""
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.constants import (
    REPOSITORY_PATH,
    RPM,
    RPM_MIRRORLIST_BAD,
    RPM_MIRRORLIST_GOOD,
    RPM_MIRRORLIST_MIXED,
    RPM_UNSIGNED_URL,
)
from pulp_smash.exceptions import TaskReportError
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _gen_rel_url():
    """Generate a relative URL."""
    return utils.uuid4() + '/'


class UtilsMixin(object):
    """A mixin providing methods to the test cases in this module.

    Any class inheriting from this mixin must also inherit from
    ``unittest.TestCase`` or a compatible clone.
    """

    def create_repo(self, cfg, feed, relative_url=None):
        """Create an RPM repository with a yum importer and distributor.

        In addition, schedule the repository for deletion with ``addCleanup``.

        :param pulp_smash.config.ServerConfig cfg: The Pulp server on which to
            create a repository.
        :param feed: A value for the yum importer's ``feed`` option.
        :param relative_url: A value for the yum distributor's ``relative_url``
            option. If ``None``, this option is not passed to Pulp.
        :returns: The repository's href.
        """
        body = gen_repo()
        body['importer_config']['feed'] = feed
        distributor = gen_distributor()
        if relative_url is not None:
            distributor['distributor_config']['relative_url'] = relative_url
        body['distributors'] = [distributor]
        client = api.Client(cfg, api.json_handler)
        repo_href = client.post(REPOSITORY_PATH, body)['_href']
        self.addCleanup(client.delete, repo_href)
        return repo_href

    @staticmethod
    def publish_repo(cfg, repo_href):
        """Publish a repository.

        The given repository should have only one distributor.

        :param pulp_smash.config.ServerConfig cfg: The Pulp server on which the
            repository is hosted.
        :param repo_href: The href of the repository to publish.
        :returns: The decoded body of the server's reponse. (A call report.)
        """
        client = api.Client(cfg, api.json_handler)
        repo = client.get(repo_href, params={'details': True})
        assert len(repo['distributors']) == 1
        return client.post(urljoin(repo_href, 'actions/publish/'), {
            'id': repo['distributors'][0]['id'],
        })

    @staticmethod
    def get_unit(cfg, repo_href, unit_name):
        """Download an RPM from a published repository.

        The given repository should have only one distributor.

        :param pulp_smash.config.ServerConfig cfg: The Pulp server on which the
            repository is hosted.
        :param repo_href: The href of the published repository.
        :param unit_name: The name of the content unit in the published
            repository.
        :returns: A binary blob.
        """
        client = api.Client(cfg)
        repo = client.get(repo_href, params={'details': True}).json()
        assert len(repo['distributors']) == 1
        path = urljoin(
            '/pulp/repos/',
            repo['distributors'][0]['config']['relative_url'],
        )
        path = urljoin(path, unit_name)
        return client.get(path).content

    def check_issue_2277(self, cfg):
        """Skip the current test method if Pulp `issue #2277`_ affects us.

        .. _issue #2277: https://pulp.plan.io/issues/2277
        """
        if (cfg.version >= Version('2.10') and
                cfg.version < Version('2.11') and
                selectors.bug_is_untestable(2277, cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2277')

    def check_issue_2321(self, cfg):
        """Skip the current test method if Pulp `issue #2321`_ affects us.

        .. _issue #2321: https://pulp.plan.io/issues/2321
        """
        if (cfg.version >= Version('2.11') and
                selectors.bug_is_untestable(2321, cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2321')

    def check_issue_2326(self, cfg):
        """Skip the current test method if Pulp `issue #2326`_ affects us.

        .. _issue #2326: https://pulp.plan.io/issues/2326
        """
        if (cfg.version >= Version('2.11') and
                selectors.bug_is_untestable(2326, cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2326')


class GoodMirrorlistTestCase(UtilsMixin, unittest.TestCase):
    """Create a repository that references a "good" mirrorlist file.

    Do the following:

    1. Create a repository. Make its importer ``feed`` option reference a
       "good" mirrorlist file.
    2. Sync and publish the repository.
    3. Download and verify a file from the published repository.
    """

    def test_all(self):
        """Execute the test case business logic."""
        cfg = config.get_config()
        self.check_issue_2277(cfg)
        self.check_issue_2326(cfg)
        repo_href = self.create_repo(cfg, RPM_MIRRORLIST_GOOD)
        utils.sync_repo(cfg, repo_href)
        self.publish_repo(cfg, repo_href)
        actual_rpm = self.get_unit(cfg, repo_href, RPM)
        target_rpm = utils.http_get(RPM_UNSIGNED_URL)
        self.assertEqual(actual_rpm, target_rpm)


class GoodRelativeUrlTestCase(UtilsMixin, unittest.TestCase):
    """Like :class:`GoodMirrorlistTestCase`, but pass ``relative_url`` too."""

    def test_all(self):
        """Execute the test case business logic."""
        cfg = config.get_config()
        self.check_issue_2277(cfg)
        self.check_issue_2326(cfg)
        repo_href = self.create_repo(cfg, RPM_MIRRORLIST_GOOD, _gen_rel_url())
        utils.sync_repo(cfg, repo_href)
        self.publish_repo(cfg, repo_href)
        actual_rpm = self.get_unit(cfg, repo_href, RPM)
        target_rpm = utils.http_get(RPM_UNSIGNED_URL)
        self.assertEqual(actual_rpm, target_rpm)


class MixedMirrorlistTestCase(UtilsMixin, unittest.TestCase):
    """Create a repository that references a "mixed" mirrorlist file.

    1. Create a repository. Make its importer ``feed`` option reference a
       "mixed" mirrorlist file.
    2. Sync and publish the repository.
    3. Download and verify a file from the published repository.
    """

    def test_all(self):
        """Execute the test case business logic."""
        cfg = config.get_config()
        self.check_issue_2277(cfg)
        self.check_issue_2321(cfg)
        repo_href = self.create_repo(cfg, RPM_MIRRORLIST_MIXED)
        utils.sync_repo(cfg, repo_href)
        self.publish_repo(cfg, repo_href)
        actual_rpm = self.get_unit(cfg, repo_href, RPM)
        target_rpm = utils.http_get(RPM_UNSIGNED_URL)
        self.assertEqual(actual_rpm, target_rpm)


class MixedRelativeUrlTestCase(UtilsMixin, unittest.TestCase):
    """Like :class:`MixedMirrorlistTestCase`, but pass ``relative_url`` too."""

    def test_all(self):
        """Execute the test case business logic."""
        cfg = config.get_config()
        self.check_issue_2277(cfg)
        self.check_issue_2321(cfg)
        repo_href = self.create_repo(cfg, RPM_MIRRORLIST_MIXED, _gen_rel_url())
        utils.sync_repo(cfg, repo_href)
        self.publish_repo(cfg, repo_href)
        actual_rpm = self.get_unit(cfg, repo_href, RPM)
        target_rpm = utils.http_get(RPM_UNSIGNED_URL)
        self.assertEqual(actual_rpm, target_rpm)


class BadMirrorlistTestCase(UtilsMixin, unittest.TestCase):
    """Create a repository that references a "bad" mirrorlist file.

    Do the following:

    1. Create a repository. Make its importer ``feed`` option reference a "bad"
       mirrorlist file.
    2. Sync the repository. Expect a failure.
    """

    def test_all(self):
        """Execute the test case business logic."""
        cfg = config.get_config()
        repo_href = self.create_repo(cfg, RPM_MIRRORLIST_BAD)
        with self.assertRaises(TaskReportError):
            utils.sync_repo(cfg, repo_href)


class BadRelativeUrlTestCase(UtilsMixin, unittest.TestCase):
    """Like :class:`BadMirrorlistTestCase`, but pass ``relative_url`` too."""

    def test_all(self):
        """Execute the test case business logic."""
        cfg = config.get_config()
        repo_href = self.create_repo(cfg, RPM_MIRRORLIST_BAD, _gen_rel_url())
        with self.assertRaises(TaskReportError):
            utils.sync_repo(cfg, repo_href)
