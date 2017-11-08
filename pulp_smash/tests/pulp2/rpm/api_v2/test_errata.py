"""Test whether applying an ``Errata`` will update an RPM package version."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM_UNSIGNED_FEED_URL
from pulp_smash.tests.pulp2.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.pulp2.rpm.utils import (
    gen_yum_config_file,
    get_rpm_names_versions,
)
from pulp_smash.tests.pulp2.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class ErrataLatestPackageVersionTestCase(unittest.TestCase):
    """Test whether applying an Errata will update a RPM package version."""

    def test_all(self):
        """Test whether applying an Errata will update a RPM package version.

        This test targets the following issue:

        * `Pulp Smash #760 <https://github.com/PulpQE/pulp-smash/issues/760>`_

        Do the following:

        1. Create, sync and publish a repository with ``Errata``, and RPM
           packages.
           Two of these RPMs have the **same name**, and **different
           versions**.
           The newest version is part of the ``Errata``.
        2. Install the oldest version of the aforementioned RPM.
        3. Apply the ``Errata``, and verify that latest version of previous
           installed package was updated properly.
        """
        # Create, sync and publish a repository.
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        pkg_mgr = cli.PackageManager(cfg)
        sudo = '' if utils.is_root(cfg) else 'sudo '
        verify = cfg.get_systems('api')[0].roles['api'].get('verify')
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo)

        # Pick a RPM with two versions.
        rpm_name = 'walrus'
        rpm_versions = get_rpm_names_versions(cfg, repo['id'])[rpm_name]
        cli_client = cli.Client(
            cfg,
            cli.code_handler,
            pulp_system=cfg.get_systems('shell')[0]
        )
        repo_path = gen_yum_config_file(
            cfg,
            baseurl=urljoin(
                cfg.get_base_url(),
                ('pulp/repos/' +
                 repo['distributors'][0]['config']['relative_url'])
            ),
            enabled=1,
            gpgcheck=0,
            metadata_expire=0,  # force metadata to load every time
            repositoryid=repo['id'],
            sslverify='yes' if verify else 'no',
        )
        self.addCleanup(
            cli_client.run,
            '{}rm {}'.format(sudo, repo_path).split()
        )

        # Install old version of package on a host.
        pkg_mgr.install((rpm_name + '-' + rpm_versions[0]))
        self.addCleanup(pkg_mgr.uninstall, rpm_name)
        cli_client.run(('rpm', '-q', (rpm_name + '-' + rpm_versions[0])))

        # Apply Errata.
        pkg_mgr.upgrade(('--advisory', 'RHEA-2012:0055'))
        rpm = cli_client.run(('rpm', '-q', rpm_name))

        # Verify that the latest version of package was updated.
        self.assertIn(rpm_versions[1], rpm.stdout)
