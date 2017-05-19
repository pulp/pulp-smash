# coding=utf-8
"""Test the CRUD API endpoints `OSTree`_ `repositories`_.

This module assumes that the tests in
:mod:`pulp_smash.tests.platform.api_v2.test_repository` hold true. The
following trees of assumptions are explored in this module::

    It is possible to create an OSTree repo with feed (CreateTestCase).
    It is possible to create a repository without a feed (CreateTestCase).
      It is possible to create distributors for a repo
        It is not possible to create distributors to have conflicting paths
        It is not possible to update distrubutors to have conflicting paths

.. _OSTree:
    http://docs.pulpproject.org/plugins/pulp_ostree/
.. _repositories:
   http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/cud.html
"""
from urllib.parse import urljoin

from packaging.version import Version
from requests.exceptions import HTTPError

from pulp_smash import api, exceptions, selectors, utils
from pulp_smash.constants import REPOSITORY_PATH
from pulp_smash.tests.ostree.utils import gen_repo
from pulp_smash.tests.ostree.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


def _gen_distributor(relative_path):
    """Return a dict for use in creating a distributor."""
    return {
        'config': {},
        'distributor_config': {'relative_path': relative_path},
        'distributor_type_id': 'ostree_web_distributor',
    }


def _gen_rel_path(segments=2):
    """Return a semi-random relative path."""
    return '/'.join((utils.uuid4() for _ in range(segments)))


class CrudTestCase(utils.BaseAPICrudTestCase):
    """CRUD a minimal OSTree repository."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        return gen_repo()

    @staticmethod
    def update_body():
        """Return a dict for creating a repository."""
        return {'delta': {'display_name': utils.uuid4()}}


class CrudWithFeedTestCase(CrudTestCase):
    """CRUD an OSTree repository with a feed."""

    @staticmethod
    def create_body():
        """Return a dict, with a feed, for creating a repository."""
        body = CrudTestCase.create_body()
        body['importer_config'] = {'feed': utils.uuid4()}
        return body


class CreateDistributorsTestCase(utils.BaseAPITestCase):
    """Show Pulp can create OSTree distributors and prevent path conflicts.

    This test case targets:

    * `Pulp #1106 <https://pulp.plan.io/issues/1106>`_
    * `Pulp #2769 <https://pulp.plan.io/issues/2769>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create a pair of repositories.

        Ensure the first repo has a distributor with a relative path.
        Succeeding tests will give the second repository distributors with
        relative paths, where those paths may or may not conflict with the
        first repository's distributor's relative path. This test splits the
        distributors across two repositories to ensure that Pulp correctly
        checks new relative paths against the existing relative paths in all
        repositories.
        """
        super().setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        bodies = tuple(gen_repo() for _ in range(2))
        bodies[0]['distributors'] = [_gen_distributor(_gen_rel_path())]
        cls.repos = []
        try:
            for body in bodies:
                repo = client.post(REPOSITORY_PATH, body)
                cls.resources.add(repo['_href'])
                cls.repos.append(
                    client.get(repo['_href'], params={'details': True})
                )
        except:
            cls.tearDownClass()
            raise

    def test_valid_v1(self):
        """Create a distributor whose relative path is valid.

        Create a unique relative path.  For example, if an existing relative
        path is ``foo/bar``, then this relative path might be ``biz/baz``.
        """
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(self.repos[1]['_href'], 'distributors/')
        body = _gen_distributor(_gen_rel_path())
        client.post(path, body)

    def test_valid_v2(self):
        """Create a distributor whose relative path is valid.

        Create a relative path that contains three segments. Most other tests
        in this module have relative paths with two segments.
        """
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(self.repos[1]['_href'], 'distributors/')
        body = _gen_distributor(_gen_rel_path(3))
        client.post(path, body)

    def test_invalid_v1(self):
        """Create a distributor whose relative path is invalid.

        Re-use the same relative path. For example, if an existing relative
        path is ``foo/bar``, then this relative path would be ``foo/bar``.
        """
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_untestable(2769, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2769')
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(self.repos[1]['_href'], 'distributors/')
        body = _gen_distributor(
            self.repos[0]['distributors'][0]['config']['relative_path']
        )
        with self.assertRaises(HTTPError):
            client.post(path, body)

    def test_invalid_v2(self):
        """Create a distributor whose relative path is invalid.

        Extend an existing relative path. For example, if an existing relative
        path is ``foo/bar``, then this relative path would be ``foo/bar/biz``.
        """
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_untestable(2769, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2769')
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(self.repos[1]['_href'], 'distributors/')
        body = _gen_distributor('/'.join((
            self.repos[0]['distributors'][0]['config']['relative_path'],
            utils.uuid4()
        )))
        with self.assertRaises(HTTPError):
            client.post(path, body)

    def test_invalid_v3(self):
        """Create a distributor whose relative path is invalid.

        Prepend a slash onto an existing relative path. For example, if an
        existing relative path is ``foo/bar``, then this relative path would be
        ``/foo/bar``.
        """
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_untestable(2769, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2769')
        client = api.Client(self.cfg, api.json_handler)
        path = urljoin(self.repos[1]['_href'], 'distributors/')
        body = _gen_distributor(
            '/' + self.repos[0]['distributors'][0]['config']['relative_path']
        )
        with self.assertRaises(HTTPError):
            client.post(path, body)


class UpdateDistributorsTestCase(utils.BaseAPITestCase):
    """Test the update of ostree distributors.

    This test case targets:

    * `Pulp #1106 <https://pulp.plan.io/issues/1106>`_
    * `Pulp #2769 <https://pulp.plan.io/issues/2769>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create a pair of repositories.

        Ensure each repo has a distributor with a relative path. Succeeding
        tests will update the second repository's distributor with varying
        relative paths, where those paths may or may not conflict with the
        first repository's distributor's relative path. This test splits the
        distributors across two repositories to ensure that Pulp correctly
        checks new relative paths against the existing relative paths in all
        repositories.
        """
        super().setUpClass()
        client = api.Client(cls.cfg, api.json_handler)
        cls.repos = []
        try:
            for _ in range(2):
                body = gen_repo()
                body['distributors'] = [_gen_distributor(_gen_rel_path())]
                repo = client.post(REPOSITORY_PATH, body)
                cls.resources.add(repo['_href'])
                cls.repos.append(
                    client.get(repo['_href'], params={'details': True})
                )
        except:
            cls.tearDownClass()
            raise

    def test_valid_v1(self):
        """Update a distributor's relative path with a valid value.

        Use a unique value for the new relative path. For example, if an
        existing relative path is ``foo/bar``, then the new relative path might
        be ``biz/baz``.
        """
        # update
        client = api.Client(self.cfg, api.json_handler)
        body = {'distributor_config': {'relative_path': _gen_rel_path()}}
        client.put(self.repos[1]['distributors'][0]['_href'], body)

        # verify
        repo = client.get(self.repos[1]['_href'], params={'details': True})
        self.assertEqual(
            repo['distributors'][0]['config']['relative_path'],
            body['distributor_config']['relative_path'],
        )

    def test_valid_v2(self):
        """Update a distributor's relative path with a valid value.

        Use a three-segment value for the new relative path. Most other tests
        in this module have relative paths with two segments.
        """
        # update
        client = api.Client(self.cfg, api.json_handler)
        body = {'distributor_config': {'relative_path': _gen_rel_path(3)}}
        client.put(self.repos[1]['distributors'][0]['_href'], body)

        # verify
        repo = client.get(self.repos[1]['_href'], params={'details': True})
        self.assertEqual(
            repo['distributors'][0]['config']['relative_path'],
            body['distributor_config']['relative_path'],
        )

    def test_invalid_v1(self):
        """Update a distributor's relative path with an invalid value.

        Re-use an existing relative path. For example, if an existing relative
        path is ``foo/bar``, then this relative path would be ``foo/bar``.
        """
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_untestable(2769, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2769')

        # update
        client = api.Client(self.cfg, api.json_handler)
        old_path = self.repos[1]['distributors'][0]['config']['relative_path']
        new_path = self.repos[0]['distributors'][0]['config']['relative_path']
        with self.assertRaises(exceptions.TaskReportError):
            client.put(self.repos[1]['distributors'][0]['_href'], {
                'distributor_config': {'relative_path': new_path}
            })

        # verify
        repo = client.get(self.repos[1]['_href'], params={'details': True})
        self.assertEqual(
            repo['distributors'][0]['config']['relative_path'],
            old_path
        )

    def test_invalid_v2(self):
        """Update a distributor's relative path with an invalid value.

        Extend an existing relative path. For example, if an existing relative
        path is ``foo/bar``, then this relative path would be ``foo/bar/biz``.
        """
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_untestable(2769, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2769')

        # update
        client = api.Client(self.cfg, api.json_handler)
        old_path = self.repos[1]['distributors'][0]['config']['relative_path']
        new_path = '/'.join((
            self.repos[0]['distributors'][0]['config']['relative_path'],
            utils.uuid4(),
        ))
        with self.assertRaises(exceptions.TaskReportError):
            client.put(self.repos[1]['distributors'][0]['_href'], {
                'distributor_config': {'relative_path': new_path}
            })

        # verify
        repo = client.get(self.repos[1]['_href'], params={'details': True})
        self.assertEqual(
            repo['distributors'][0]['config']['relative_path'],
            old_path
        )

    def test_invalid_v3(self):
        """Update a distributor's relative path with an invalid value.

        Prepend a slash to an existing relative path. For example, if an
        existing relative path is ``foo/bar``, then this relative path would be
        ``/foo/bar``.
        """
        if (self.cfg.version >= Version('2.14') and
                selectors.bug_is_untestable(2769, self.cfg.version)):
            self.skipTest('https://pulp.plan.io/issues/2769')

        # update
        client = api.Client(self.cfg, api.json_handler)
        old_path = self.repos[1]['distributors'][0]['config']['relative_path']
        new_path = (
            '/' + self.repos[0]['distributors'][0]['config']['relative_path']
        )
        with self.assertRaises(exceptions.TaskReportError):
            client.put(self.repos[1]['distributors'][0]['_href'], {
                'distributor_config': {'relative_path': new_path}
            })

        # verify
        repo = client.get(self.repos[1]['_href'], params={'details': True})
        self.assertEqual(
            repo['distributors'][0]['config']['relative_path'],
            old_path
        )
