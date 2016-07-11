# coding=utf-8
"""Tests that copy units from one repository to another."""
from __future__ import unicode_literals

import inspect
import os
import random
import subprocess

import unittest2

from pulp_smash import cli, config, constants, selectors, utils
from pulp_smash.compat import StringIO, urljoin
from pulp_smash.tests.rpm.cli.utils import count_langpacks
from pulp_smash.tests.rpm.utils import set_up_module
from pulp_smash.utils import is_root

_REPO_ID = utils.uuid4()
"""The ID of the repository created by ``setUpModule``."""


def generate_repo_file(server_config, name, **kwargs):
    """Generate a repository file and returns its remote path.

    :param server_config: A :class:`pulp_smash.config.ServerConfig` object.
    :param name: file name and repo id (string inside []).
    :param kwargs: each item will be converted to repository properties where
        the key is the property name and the value its value.
    :returns: the remote path of the created repository file.
    """
    repo = StringIO()
    repo.write('[{}]\n'.format(name))
    path = os.path.join(
        '{}'.format('/etc/yum.repos.d/'), '{}.repo'.format(name))
    if 'name' not in kwargs:
        repo.write('{}: {}\n'.format('name', name))
    for key, value in kwargs.items():
        repo.write('{}: {}\n'.format(key, value))
    client = cli.Client(server_config)
    sudo = '' if is_root(server_config) else 'sudo '
    client.machine.session().run(
        'echo "{}" | {}tee {} > /dev/null'.format(
            repo.getvalue(),
            sudo,
            path
        )
    )
    repo.close()
    return path


def _get_rpm_names_versions(server_config, repo_id):
    """Get a dict of repo's RPMs with names as keys, mapping to version lists.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param repo_id: A RPM repository ID.
    :returns: The names of all modules in a repository, with a list of all
        versions mapped to each module, as an ``dict``.
    """
    keyword = 'Filename:'
    completed_proc = cli.Client(server_config).run(
        'pulp-admin rpm repo content rpm --repo-id {}'.format(repo_id).split()
    )
    filenames = [
        line.lstrip(keyword).strip()
        for line in completed_proc.stdout.splitlines()
        if keyword in line
    ]
    assert len(filenames) > 0
    rpms = {}
    for filename in filenames:
        # Example of a filename string: 'walrus-0.71-1.noarch.rpm'.
        filename_parts = filename.split('-')[:-1]
        name = '-'.join(filename_parts[:-1])
        version = filename_parts[-1]
        rpms.setdefault(name, []).append(version)
    return rpms


def setUpModule():  # pylint:disable=invalid-name
    """Possibly skip tests. Create and sync an RPM repository.

    Skip tests in this module if the RPM plugin is not installed on the target
    Pulp server. Then create an RPM repository with a feed and sync it. Test
    cases may copy data from this repository but should **not** change it.
    """
    set_up_module()
    cfg = config.get_config()
    client = cli.Client(config.get_config())

    # log in, then create repository
    utils.pulp_admin_login(cfg)
    client.run(
        'pulp-admin rpm repo create --repo-id {} --feed {}'
        .format(_REPO_ID, constants.RPM_FEED_URL).split()
    )

    # If setUpModule() fails, tearDownModule() isn't run. In addition, we can't
    # use addCleanup(), as it's an instance method. If this set-up procedure
    # grows, consider implementing a stack of tear-down steps instead.
    try:
        client.run(
            'pulp-admin rpm repo sync run --repo-id {}'
            .format(_REPO_ID).split()
        )
    except subprocess.CalledProcessError:
        client.run(
            'pulp-admin rpm repo delete --repo-id {}'.format(_REPO_ID).split()
        )
        raise


def tearDownModule():  # pylint:disable=invalid-name
    """Delete the repository created by ``setUpModule``."""
    cli.Client(config.get_config()).run(
        'pulp-admin rpm repo delete --repo-id {}'.format(_REPO_ID).split()
    )


class CopyBaseTestCase(unittest2.TestCase):
    """An abstract base class for test cases that copy units between repos."""

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        if inspect.getmro(cls)[0] == CopyBaseTestCase:
            raise unittest2.SkipTest('Abstract base class.')
        cls.cfg = config.get_config()
        cls.repo_id = utils.uuid4()
        cli.Client(cls.cfg).run(
            'pulp-admin rpm repo create --repo-id {}'
            .format(cls.repo_id).split()
        )

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        cli.Client(cls.cfg).run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )


class CopyTestCase(CopyBaseTestCase):
    """Copy a "chimpanzee" unit from one repository to another.

    This test case verifies that it is possible to use the ``pulp-admin rpm
    repo copy`` command to copy a single unit from one repository to another.
    """

    @classmethod
    def setUpClass(cls):
        """Copy a unit into a repository and list the units in it."""
        super(CopyTestCase, cls).setUpClass()
        cli.Client(cls.cfg).run(
            'pulp-admin rpm repo copy rpm --from-repo-id {} --to-repo-id {} '
            '--str-eq name=chimpanzee'.format(_REPO_ID, cls.repo_id).split()
        )

    def test_units_copied(self):
        """Assert only the "chimpanzee" unit is in the target repository."""
        response = cli.Client(self.cfg).run(
            'pulp-admin rpm repo content rpm --repo-id {}'
            .format(self.repo_id).split()
        )
        names = tuple((
            line.split()[1] for line in response.stdout.split('\n')
            if line.startswith('Name:')
        ))
        self.assertEqual(names, ('chimpanzee',))


class CopyRecursiveTestCase(CopyBaseTestCase):
    """Recursively copy a "chimpanzee" unit from one repository to another.

    This test case verifies that it is possible to use the ``pulp-admin rpm
    repo copy`` command to recursively copy units from one repository to
    another. See `Pulp Smash #107`_.

    .. _Pulp Smash #107: https://github.com/PulpQE/pulp-smash/issues/107
    """

    @classmethod
    def setUpClass(cls):
        """Recursively copy a unit into a repo and list the units in it."""
        super(CopyRecursiveTestCase, cls).setUpClass()
        if selectors.bug_is_untestable(1895, cls.cfg.version):
            raise unittest2.SkipTest('https://pulp.plan.io/issues/1895')
        cli.Client(cls.cfg).run(
            'pulp-admin rpm repo copy rpm --from-repo-id {} --to-repo-id {} '
            '--str-eq name=chimpanzee --recursive'
            .format(_REPO_ID, cls.repo_id).split()
        )

    def test_units_copied(self):
        """Assert only one "walrus" unit has been copied to the target repo.

        There are two "walrus" units in the source repository, Only the newest
        version should be copied over.
        """
        response = cli.Client(self.cfg).run(
            'pulp-admin rpm repo content rpm --repo-id {}'
            .format(self.repo_id).split()
        )
        names = tuple((
            line.split()[1] for line in response.stdout.split('\n')
            if line.startswith('Name:')
        ))
        self.assertEqual(names.count('walrus'), 1, names)


class CopyLangpacksTestCase(CopyBaseTestCase):
    """Copy langpacks from one repository to another.

    This test case verifies that it is possible to use the ``pulp-admin rpm
    repo copy langpacks`` command to copy langpacks from one repository to
    another. See `Pulp Smash #255`_.

    .. _Pulp Smash #255: https://github.com/PulpQE/pulp-smash/issues/255
    """

    def test_copy_langpacks(self):
        """Copy langpacks from one repository to another.

        Assert that:

        * ``pulp-admin`` does not produce any errors.
        * A non-zero number of langpacks are present in the target repository.
        """
        if selectors.bug_is_untestable(1367, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1367')
        completed_proc = cli.Client(self.cfg).run(
            'pulp-admin rpm repo copy langpacks '
            '--from-repo-id {} --to-repo-id {}'
            .format(_REPO_ID, self.repo_id).split()
        )
        with self.subTest(comment='verify copy command stdout'):
            self.assertNotIn('Task Failed', completed_proc.stdout)
        with self.subTest(comment='verify langpack count in repo'):
            self.assertGreater(
                count_langpacks(self.cfg, self.repo_id),
                0,
            )


class CopyAndPublishTwoVersionsRepoTestCase(CopyBaseTestCase):
    """Test whether a repo can copy two versions of RPMs and publish itself.

    This test case targets `Pulp Smash #311`_. The test steps are as following:

    1. Create a repo1 and sync from upstream.
    2. Find a RPM that has two different versions in this repo.
    3. Create a new repo2 and copy the older of the RPM version into it.
    4. Publish the repo2 as a host.
    5. Copy a newer version into the repo2 and re-publish.
    6. Yum update on the client and verify update would succeed.

    Note that the 1st repo `_REPO_ID` has been synced in `setUpModule()`,
    while the 2nd repo `repo_id` has been created by base class without
    a feed.

    .. _Pulp Smash #311: https://github.com/PulpQE/pulp-smash/issues/311
    """

    @classmethod
    def setUpClass(cls):
        """Find a RPM with more than one version on repo1."""
        super(CopyAndPublishTwoVersionsRepoTestCase, cls).setUpClass()
        cls.client = cli.Client(cls.cfg)
        cls.sudo = '' if is_root(cls.cfg) else 'sudo '
        # Retrieve all modules with multiple versions in the repo1.
        rpms = {
            key: value
            for key, value in _get_rpm_names_versions(
                cls.cfg, _REPO_ID).items()
            if len(value) > 1
        }
        assert len(rpms) > 0
        # Choose a random module with multiple versions.
        cls.rpm_name = random.choice(list(rpms.keys()))
        versions = rpms[cls.rpm_name]
        versions.sort()
        cls.rpm_old_version = versions[-2]
        cls.rpm_new_version = versions[-1]

    def test_update_copied_rpm(self):
        """Check if a client can update a copied RPM.

        Do the following:

        1. Copy an old version of a RPM and its dependencies from one repo to
           another.
        2. Publish the target repository.
        3. Install the RPM.
        4. Copy an updated version of the RPM copied on step 1.
        5. Publish the target repository again.
        6. Check if the yum will install the updated RPM.
        """
        # Copy and publish the old RPM package version.
        self._copy_and_publish(self.rpm_name, self.rpm_old_version)

        repo_path = generate_repo_file(
            self.cfg,
            self.repo_id,
            baseurl=urljoin(
                self.cfg.base_url, 'pulp/repos/{}'.format(self.repo_id)),
            enabled=1,
            gpgcheck=0,
            metadata_expire=0,  # force metadata to load every time
        )
        self.addCleanup(
            self.client.run,
            '{}rm {}'.format(self.sudo, repo_path).split()
        )
        self.client.run(
            '{}yum install -y {}'
            .format(self.sudo, self.rpm_name).split()
        )
        self.addCleanup(
            self.client.run,
            '{}yum remove -y {}'.format(self.sudo, self.rpm_name).split()
        )
        self.assertEqual(
            cli.Client(self.cfg, cli.echo_handler).run(
                'rpm -q {}'.format(self.rpm_name).split()).returncode,
            0
        )
        self._copy_and_publish(self.rpm_name, self.rpm_new_version)
        # Execute `yum update` on the RPM.
        completed_proc = self.client.run(
            '{}yum -y update {}'
            .format(self.sudo, self.rpm_name).split()
        )
        # Check if the update succeeds; it should have updates.
        self.assertNotIn('Nothing to do.', completed_proc.stdout)

    def _copy_and_publish(self, rpm_name, rpm_version):
        """Copy the RPM with given name and version into repo2 and publish it.

        :param rpm_name: The name of target module.
        :param rpm_version: The version of target module.
        """
        # Copy the package and its dependencies to the new repo
        self.client.run(
            'pulp-admin rpm repo copy rpm --from-repo-id {} --to-repo-id {} '
            '--str-eq=name={} --str-eq=version={} --recursive'
            .format(_REPO_ID, self.repo_id, rpm_name, rpm_version).split()
        )

        # Search for the RPM's name/version in repo2's content.
        result = self.client.run(
            'pulp-admin rpm repo content rpm --repo-id {} --str-eq name={} '
            '--str-eq version={}'
            .format(self.repo_id, rpm_name, rpm_version).split()
        )
        with self.subTest(comment='rpm name present'):
            self.assertIn(rpm_name, result.stdout)
        with self.subTest(comment='rpm version present'):
            self.assertIn(rpm_version, result.stdout)

        # Publish repo2 and verify no errors.
        completed_proc = self.client.run(
            'pulp-admin rpm repo publish run --repo-id {}'
            .format(self.repo_id).split()
        )
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn(
                    'Task Failed', getattr(completed_proc, stream)
                )
