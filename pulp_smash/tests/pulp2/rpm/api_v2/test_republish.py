# coding=utf-8
"""Tests that re-publish repositories."""
import os
import random
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import (
    RPM2_UNSIGNED_URL,
    RPM_UNSIGNED_FEED_URL,
    RPM_UNSIGNED_URL,
)
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import (
    publish_repo,
    search_units,
    sync_repo,
    upload_import_unit,
)
from pulp_smash.tests.pulp2.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_unit,
)
from pulp_smash.tests.pulp2.rpm.utils import (
    check_issue_2277,
    check_issue_2620,
    check_issue_3104,
)
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class UnassociateTestCase(unittest.TestCase):
    """Republish a repository after removing content.

    Specifically, this test case does the following:

    1. Create, populate and publish a repository.
    2. Pick a content unit from the repository and verify it can be downloaded.
    3. Remove the content unit from the repository, and re-publish it, and
       verify that it can't be downloaded.
    """

    def test_all(self):
        """Republish a repository after removing content."""
        cfg = config.get_config()
        if check_issue_3104(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/3104')
        if check_issue_2277(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        if check_issue_2620(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')

        # Create, sync and publish a repository.
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)

        # Pick a random content unit and verify it's accessible.
        unit = random.choice(
            search_units(cfg, repo, {'type_ids': ('rpm',)})
        )
        filename = unit['metadata']['filename']
        get_unit(cfg, repo['distributors'][0], filename)

        # Remove the content unit and verify it's inaccessible.
        client.post(
            urljoin(repo['_href'], 'actions/unassociate/'),
            {'criteria': {'filters': {'unit': {'filename': filename}}}},
        )
        publish_repo(cfg, repo)
        with self.assertRaises(KeyError):
            get_unit(cfg, repo['distributors'][0], filename)


class RemoveOldRepodataTestCase(unittest.TestCase):
    """Check whether old repodata is removed when it should be.

    According to `Pulp #2788`_, Pulp will retain unnecessary metadata files
    from previous publishes. This can be problematic for long-lived
    repositories, as they will eventually be filled with gobs and gobs of
    unnecessary data. The fix is to introduce the ``remove_old_repodata`` and
    ``remove_old_repodata_threshold`` options, which control for how long old
    metadata is retained. Each test in this test case does the following:

    1. Create a repository. Ensure the distributor has several interesting
       settings, including ``generate_sqlite`` being true.
    2. Upload an RPM, publish the repo, and count the number of metadata files.
       Assert that there are metadata files.
    3. Do it again. Either assert that there are more metadata files or that
       there are the same number of metadata files, depending on the
       distributor settings.

    .. _Pulp #2788: https://pulp.plan.io/issues/2788
    """

    @classmethod
    def setUpClass(cls):
        """Set class-wide variables."""
        cls.cfg = config.get_config()

    def test_cleanup_disabled(self):
        """Set ``remove_old_repodata`` to false, and the threshold to 0.

        Assert that there are more metadata files after the second publish.
        """
        if selectors.bug_is_untestable(2788, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2788')
        found = self.do_test({
            'generate_sqlite': True,
            'remove_old_repodata': False,
            'remove_old_repodata_threshold': 0,
        })
        self.assertGreater(len(found[0]), 0, found[0])
        self.assertLess(len(found[0]), len(found[1]), found[0])

    def test_cleanup_now(self):
        """Set ``remove_old_repodata`` to true, and the threshold to 0.

        Assert that there are the same number of metadata files after the
        second publish.
        """
        if selectors.bug_is_untestable(2788, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2788')
        found = self.do_test({
            'generate_sqlite': True,
            'remove_old_repodata_threshold': 0,
        })
        self.assertGreater(len(found[0]), 0, found[0])
        self.assertEqual(len(found[0]), len(found[1]), found[0])

    def test_cleanup_later(self):
        """Set ``remove_old_repodata`` to true, and the threshold to 3600.

        Assert there are more metadata files after the second publish.
        """
        if selectors.bug_is_untestable(2788, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2788')
        found = self.do_test({
            'generate_sqlite': True,
            'remove_old_repodata_threshold': 3600,
        })
        self.assertGreater(len(found[0]), 0, found[0])
        self.assertLess(len(found[0]), len(found[1]), found[0])

    def test_cleanup_default(self):
        """Set ``remove_old_repodata`` to true, and the threshold at default.

        Assert there are more metadata files after the second publish.
        """
        found = self.do_test({'generate_sqlite': True})
        self.assertGreater(len(found[0]), 0, found[0])
        self.assertLess(len(found[0]), len(found[1]), found[0])

    def do_test(self, distributor_config_update):
        """Implement most of the test logic."""
        rpms = tuple(
            utils.http_get(url)
            for url in (RPM_UNSIGNED_URL, RPM2_UNSIGNED_URL)
        )

        # Create a repository.
        client = api.Client(self.cfg, api.json_handler)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        body['distributors'][0]['distributor_config'].update(
            distributor_config_update
        )
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})

        # Upload an RPM, publish the repo, and count metadata files twice.
        cli_client = cli.Client(self.cfg)
        sudo = () if utils.is_root(self.cfg) else ('sudo',)
        find_repodata_cmd = sudo + (
            'find', os.path.join(
                '/var/lib/pulp/published/yum/master/yum_distributor/',
                str(repo['id'])
            ), '-type', 'd', '-name', 'repodata'
        )
        found = []
        for rpm in rpms:
            upload_import_unit(
                self.cfg,
                rpm,
                {'unit_type_id': 'rpm'},
                repo,
            )
            publish_repo(self.cfg, repo)
            repodata_path = cli_client.run(find_repodata_cmd).stdout.strip()
            found.append(cli_client.run(sudo + (
                'find', repodata_path, '-type', 'f'
            )).stdout.splitlines())
        return found
