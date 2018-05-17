"""Test whether applying an erratum will update an RPM package version."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import RPM_LARGE_UPDATEINFO, RPM_UNSIGNED_FEED_URL
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import publish_repo, sync_repo
from pulp_smash.tests.pulp2.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_rpm_names_versions,
)
from pulp_smash.tests.pulp2.rpm.utils import gen_yum_config_file
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class ApplyErratumTestCase(unittest.TestCase):
    """Test whether applying an erratum will install referenced RPMs."""

    def test_all(self):
        """Test whether applying an erratum will install referenced RPMs.

        It does the following:

        1. Create, sync and publish a repository with errata and RPM packages.
           Two of these RPMs have the same name and different versions. The
           newest version is referenced by one of the errata.
        2. Install the older version of the aforementioned RPM.
        3. Apply the erratum, and verify that newer version of the RPM is
           installed.

        This test targets `Pulp Smash #760
        <https://github.com/PulpQE/pulp-smash/issues/760>`_.
        """
        cfg = config.get_config()
        repo = self._create_sync_publish_repo(cfg)
        self._create_repo_file(cfg, repo)

        # Install the older version of the RPM, and verify it's been installed.
        rpm_name = 'walrus'
        rpm_versions = get_rpm_names_versions(cfg, repo)[rpm_name]
        pkg_mgr = cli.PackageManager(cfg)
        pkg_mgr.install((rpm_name + '-' + rpm_versions[0]))
        self.addCleanup(pkg_mgr.uninstall, rpm_name)
        cli_client = cli.Client(cfg)
        rpm = cli_client.run(('rpm', '-q', rpm_name)).stdout.strip()
        self.assertTrue(rpm.startswith('-'.join((rpm_name, rpm_versions[0]))))

        # Apply erratum. Verify that the newer version of the RPM is installed.
        pkg_mgr.upgrade(self._get_upgrade_targets(cfg))
        rpm = cli_client.run(('rpm', '-q', rpm_name)).stdout.strip()
        self.assertTrue(rpm.startswith('-'.join((rpm_name, rpm_versions[1]))))

    def _create_sync_publish_repo(self, cfg):
        """Create, sync and publish a repository.

        Also, schedule it for deletion. Return a detailed dict of information
        about the repository.
        """
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)
        return repo

    def _create_repo_file(self, cfg, repo):
        """Create a file in ``/etc/yum.repos.d/`` referencing the repository.

        Also, schedule it for deletion. Return nothing.
        """
        verify = cfg.get_hosts('api')[0].roles['api'].get('verify')
        sudo = () if utils.is_root(cfg) else ('sudo',)
        repo_path = gen_yum_config_file(
            cfg,
            baseurl=urljoin(cfg.get_base_url(), urljoin(
                'pulp/repos/',
                repo['distributors'][0]['config']['relative_url']
            )),
            enabled=1,
            gpgcheck=0,
            metadata_expire=0,  # force metadata to load every time
            repositoryid=repo['id'],
            sslverify='yes' if verify else 'no',
        )
        self.addCleanup(cli.Client(cfg).run, sudo + ('rm', repo_path))

    def _get_upgrade_targets(self, cfg):
        """Get a tuple of upgrade targets for erratum RHEA-2012:0055."""
        erratum = 'RHEA-2012:0055'
        # Many of Pulp Smash's classes are concerned with hiding the
        # differences between different target platforms. That's the point of
        # methods like PackageManager.upgrade. But sometimes, we need to peek
        # under the hood, and this is a good example of that. Maybe
        # _get_package_manager() could be made into a public function.
        yum_or_dnf = cli.PackageManager._get_package_manager(cfg)  # pylint:disable=protected-access
        self.assertIn(yum_or_dnf, ('yum', 'dnf'))
        if yum_or_dnf == 'yum':
            return ('--advisory', erratum)
        lines = cli.Client(cfg).run((
            'dnf', '--quiet', 'updateinfo', 'list', erratum
        )).stdout.strip().splitlines()
        return tuple((line.split()[2] for line in lines))


class LargePackageListTestCase(unittest.TestCase):
    """Test syncing errata with large package list."""

    def test_all(self):
        """Test syncing errata with large package list.

        This test targets the following issue:

        * `Pulp #2681 <https://pulp.plan.io/issues/2681>`_
        * `Pulp Smash #656 <https://github.com/PulpQE/pulp-smash/issues/656>`_

        Do the following:

        1. Create two repositories, each with a feed URL of
           :data:`pulp_smash.constants.RPM_LARGE_UPDATEINFO`.
        2. Sync both repositories. Assert that each sync finishes without
           errors.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(2681, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2681')
        repos = []
        client = api.Client(cfg, api.json_handler)

        # Create repositories.
        for _ in range(2):
            body = gen_repo()
            body['importer_config']['feed'] = RPM_LARGE_UPDATEINFO
            repo = client.post(REPOSITORY_PATH, body)
            self.addCleanup(client.delete, repo['_href'])
            repos.append(repo)

        # Sync repositories.
        for repo in repos:
            report = sync_repo(cfg, repo)
            tasks = tuple(api.poll_spawned_tasks(cfg, report.json()))
            for i, task in enumerate(tasks):
                with self.subTest(i=i):
                    error_details = task['progress_report']['yum_importer']['content']['error_details']  # pylint:disable=line-too-long
                    self.assertEqual(error_details, [], task)
