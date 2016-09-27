# coding=utf-8
"""Tests for Pulp's download policies, such as "background" and "on demand".

Beware that the test cases for the "on demand" download policy will fail if
Pulp's Squid server is not configured to return an appropriate hostname or IP
when performing redirection.
"""
import hashlib
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.constants import REPOSITORY_PATH, RPM, RPM_FEED_URL, RPM_URL
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_smash.tests.rpm.utils import set_up_module


def _os_is_rhel6(server_config):
    """Return ``True`` if the server runs RHEL 6, or ``False`` otherwise."""
    response = cli.Client(server_config, cli.echo_handler).run((
        'grep',
        '-i',
        'red hat enterprise linux server release 6',
        '/etc/redhat-release',
    ))
    return response.returncode == 0


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests if the RPM plugin is not installed."""
    set_up_module()
    cfg = config.get_config()
    if cfg.version < Version('2.8'):
        raise unittest.SkipTest('This module requires Pulp 2.8 or greater.')
    if selectors.bug_is_untestable(2272, cfg.version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2272')
    if selectors.bug_is_untestable(2144, cfg.version):
        raise unittest.SkipTest('https://pulp.plan.io/issues/2144')


def _create_repo(server_config, download_policy):
    """Create an RPM repository with the given download policy.

    The repository has a valid feed and is configured to auto-publish. Return
    the JSON-decoded response body.
    """
    body = gen_repo()
    body['importer_config']['download_policy'] = download_policy
    body['importer_config']['feed'] = RPM_FEED_URL
    distributor = gen_distributor()
    distributor['auto_publish'] = True
    distributor['distributor_config']['relative_url'] = body['id']
    body['distributors'] = [distributor]
    return api.Client(server_config).post(REPOSITORY_PATH, body).json()


class BackgroundTestCase(utils.BaseAPITestCase):
    """Ensure the "background" download policy works."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a valid feed and sync it.

        Do the following:

        1. Reset Pulp, including the Squid cache.
        2. Create a repository with the "background" download policy.
        3. Sync and publish the repository.
        4. Download an RPM from the repository.
        """
        super(BackgroundTestCase, cls).setUpClass()
        if (selectors.bug_is_untestable(1905, cls.cfg.version) and
                _os_is_rhel6(cls.cfg)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1905')

        # Required to ensure content is actually downloaded.
        utils.reset_squid(cls.cfg)
        utils.reset_pulp(cls.cfg)

        # Create, sync and publish a repository.
        repo = _create_repo(cls.cfg, 'background')
        cls.resources.add(repo['_href'])
        report = utils.sync_repo(cls.cfg, repo['_href']).json()

        # Record the tasks spawned when syncing the repository, and the state
        # of the repository itself after the sync.
        client = api.Client(cls.cfg)
        cls.repo = client.get(repo['_href'], params={'details': True}).json()
        cls.tasks = tuple(api.poll_spawned_tasks(cls.cfg, report))

        # Download an RPM.
        path = urljoin('/pulp/repos/', repo['id'] + '/')
        path = urljoin(path, RPM)
        cls.rpm = client.get(path)

    def test_repo_local_units(self):
        """Assert that all content is downloaded for the repository."""
        self.assertEqual(
            self.repo['locally_stored_units'],
            sum(self.repo['content_unit_counts'].values()),
            self.repo['content_unit_counts'],
        )

    def test_request_history(self):
        """Assert that the request was serviced directly by Pulp.

        If Pulp did not have the content available locally, it would redirect
        the client to the streamer and the rpm request would contain a history
        entry for that redirect.
        """
        # HTTP 302 responses should have a "Location" header.
        history_headers = [response.headers for response in self.rpm.history]
        self.assertEqual(0, len(self.rpm.history), history_headers)

    def test_rpm_checksum(self):
        """Assert the checksum of the downloaded RPM matches the metadata."""
        actual = hashlib.sha256(self.rpm.content).hexdigest()
        expect = utils.get_sha256_checksum(RPM_URL)
        self.assertEqual(actual, expect)

    def test_spawned_download_task(self):
        """Assert that a download task was spawned as a result of the sync."""
        expected_tags = {
            'pulp:repository:' + self.repo['id'],
            'pulp:action:download',
        }

        tasks = [t for t in self.tasks if set(t['tags']) == expected_tags]
        self.assertEqual(1, len(tasks))
        self.assertEqual('finished', tasks[0]['state'])


class OnDemandTestCase(utils.BaseAPITestCase):
    """Ensure the "on demand" download policy works."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a valid feed and sync it.

        Do the following:

        1. Reset Pulp, including the Squid cache.
        2. Create a repository with the "on demand" download policy.
        3. Sync and publish the repository.
        4. Download an RPM from the published repository.
        5. Download the same RPM to ensure it is served by the cache.
        """
        super(OnDemandTestCase, cls).setUpClass()

        # Ensure `locally_stored_units` is 0 before we start.
        utils.reset_squid(cls.cfg)
        utils.reset_pulp(cls.cfg)

        # Create, sync and publish a repository.
        repo = _create_repo(cls.cfg, 'on_demand')
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Read the repository.
        client = api.Client(cls.cfg)
        cls.repo = client.get(repo['_href'], params={'details': True}).json()

        # Download the same RPM twice.
        path = urljoin('/pulp/repos/', repo['id'] + '/')
        path = urljoin(path, RPM)
        cls.rpm = client.get(path)
        cls.same_rpm = client.get(path)

    def test_local_units(self):
        """Assert no content units were downloaded besides metadata."""
        metadata_unit_count = sum([
            count for name, count in self.repo['content_unit_counts'].items()
            if name not in ('rpm', 'drpm', 'srpm')
        ])
        self.assertEqual(
            self.repo['locally_stored_units'],
            metadata_unit_count
        )

    def test_repository_units(self):
        """Assert there is at least one content unit in the repository."""
        total_units = sum(self.repo['content_unit_counts'].values())
        self.assertEqual(self.repo['total_repository_units'], total_units)

    def test_request_history(self):
        """Assert the initial request received a 302 Redirect."""
        self.assertTrue(self.rpm.history[0].is_redirect)

    def test_rpm_checksum(self):
        """Assert the checksum of the downloaded RPM matches the metadata."""
        actual = hashlib.sha256(self.rpm.content).hexdigest()
        expect = utils.get_sha256_checksum(RPM_URL)
        self.assertEqual(actual, expect)

    def test_rpm_cache_lookup_header(self):
        """Assert the first request resulted in a cache miss from Squid."""
        self.assertIn('MISS', self.rpm.headers['X-Cache-Lookup'])

    def test_rpm_cache_control_header(self):
        """Assert the request has the Cache-Control header set."""
        self.assertEqual(
            {'s-maxage=86400', 'public', 'max-age=86400'},
            set(self.rpm.headers['Cache-Control'].split(', '))
        )

    def test_same_rpm_checksum(self):
        """Assert the checksum of the second RPM matches the metadata."""
        actual = hashlib.sha256(self.same_rpm.content).hexdigest()
        expect = utils.get_sha256_checksum(RPM_URL)
        self.assertEqual(actual, expect)

    def test_same_rpm_cache_header(self):
        """Assert the second request resulted in a cache hit from Squid."""
        self.assertIn('HIT', self.same_rpm.headers['X-Cache-Lookup'])


class FixFileCorruptionTestCase(utils.BaseAPITestCase):
    """Ensure the "on demand" download policy can fix file corruption."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository and issue a task to download the repo.

        Do the following:

        1. Reset Pulp.
        2. Create a repository with the "on demand" download policy.
        3. Sync and publish the repository.
        4. Trigger a repository download.
        5. Corrupt a file in the repository.
        6. Trigger a repository download, without unit verification.
        7. Trigger a repository download, with unit verification.
        """
        super(FixFileCorruptionTestCase, cls).setUpClass()
        if (selectors.bug_is_untestable(1905, cls.cfg.version) and
                _os_is_rhel6(cls.cfg)):
            raise unittest.SkipTest('https://pulp.plan.io/issues/1905')

        # Ensure Pulp is empty of units otherwise we might just associate pre-
        # existing units.
        utils.reset_pulp(cls.cfg)

        # Create, sync and publish a repository.
        repo = _create_repo(cls.cfg, 'on_demand')
        cls.resources.add(repo['_href'])
        utils.sync_repo(cls.cfg, repo['_href'])

        # Trigger a repository download. Read the repo before and after.
        api_client = api.Client(cls.cfg, api.json_handler)
        download_path = urljoin(repo['_href'], 'actions/download/')
        params = {'details': True}
        cls.repo_pre_download = api_client.get(repo['_href'], params=params)
        api_client.post(download_path, {'verify_all_units': False})
        cls.repo_post_download = api_client.get(repo['_href'], params=params)

        # Corrupt an RPM. The file is there, but the checksum isn't right.
        rpm_abs_path = cls.get_rpm_abs_path()
        cli_client = cli.Client(cls.cfg)
        sudo = '' if utils.is_root(cls.cfg) else 'sudo '
        checksum_cmd = (sudo + 'sha256sum ' + rpm_abs_path).split()
        cls.sha_pre_corruption = cli_client.run(checksum_cmd).stdout.strip()
        cli_client.run((sudo + 'rm ' + rpm_abs_path).split())
        cli_client.run((sudo + 'touch ' + rpm_abs_path).split())
        cli_client.run((sudo + 'chown apache:apache ' + rpm_abs_path).split())
        cls.sha_post_corruption = cli_client.run(checksum_cmd).stdout.strip()

        # Trigger repository downloads that don't and do checksum files, resp.
        api_client.post(download_path, {'verify_all_units': False})
        cls.unverified_file_sha = cli_client.run(checksum_cmd).stdout.strip()
        api_client.post(download_path, {'verify_all_units': True})
        cls.verified_file_sha = cli_client.run(checksum_cmd).stdout.strip()

    @classmethod
    def get_rpm_abs_path(cls):
        """Return the absolute path to :data:`pulp_smash.constants.RPM`."""
        return cli.Client(cls.cfg).run(
            'find /var/lib/pulp/content/units/rpm/ -type f -name'
            .split() + [RPM]
        ).stdout.strip()

    def test_units_before_download(self):
        """Assert no content units were downloaded besides metadata units."""
        locally_stored_units = self.repo_pre_download['locally_stored_units']
        content_unit_counts = self.repo_pre_download['content_unit_counts']
        metadata_unit_count = sum([
            count for name, count in content_unit_counts.items()
            if name not in ('rpm', 'drpm', 'srpm')
        ])
        self.assertEqual(locally_stored_units, metadata_unit_count)

    def test_units_after_download(self):
        """Assert all units are downloaded after download_repo finishes."""
        # Support for package langpacks has been added in Pulp 2.9. In earlier
        # versions, langpacks are ignored.
        locally_stored_units = 39  # See repo['content_unit_counts']
        if self.cfg.version >= Version('2.9'):
            locally_stored_units += 1
        self.assertEqual(
            self.repo_post_download['locally_stored_units'],
            locally_stored_units,
            self.repo_post_download,
        )

    def test_corruption_occurred(self):
        """Assert corrupting a unit changes its checksum.

        This is to ensure we actually corrupted the RPM and validates further
        testing.
        """
        self.assertNotEqual(self.sha_pre_corruption, self.sha_post_corruption)

    def test_verify_all_units_false(self):
        """Verify Pulp's behaviour when ``verify_all_units`` is false.

        Assert that the checksum of the corrupted unit is unchanged, indicating
        that Pulp did not verify (or re-download) the checksum of the corrupted
        unit.
        """
        self.assertEqual(self.sha_post_corruption, self.unverified_file_sha)

    def test_verify_all_units_true(self):
        """Verify Pulp's behaviour when ``verify_all_units`` is true.

        Assert that the checksum of the corrupted unit is changed, indicating
        that Pulp did verify the checksum of the corrupted unit, and
        subsequently re-downloaded the unit.
        """
        self.assertNotEqual(self.unverified_file_sha, self.verified_file_sha)

    def test_start_end_checksums(self):
        """Verify Pulp's behaviour when ``verify_all_units`` is true.

        Assert that the pre-corruption checksum of the unit is the same as the
        post-redownload checksum of the unit.
        """
        self.assertEqual(self.sha_pre_corruption, self.verified_file_sha)
