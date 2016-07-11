# coding=utf-8
"""Tests that copy units from one repository to another."""
from __future__ import unicode_literals

import inspect
import subprocess

import unittest2

from pulp_smash import cli, config, constants, selectors, utils
from pulp_smash.compat import urljoin
from pulp_smash.tests.rpm.utils import set_up_module
from pulp_smash.tests.rpm.cli.utils import _count_langpacks

_REPO_ID = None
"""The ID of the repository created by ``setUpModule``."""


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
        line for line in completed_proc.stdout.splitlines() if keyword in line
    ]
    assert len(filenames) > 0
    rpm_dict = {}
    for file_name_str in filenames:
        # Example of a filename string: 'Filename: walrus-0.71-1.noarch.rpm'.
        name_version = file_name_str.split('-')
        rpm_dict.setdefault(
            name_version[0].split(keyword)[1].strip(),
            []
        ).append(name_version[1])
    return rpm_dict


def _copy_repo(server_config, source, destination, rpm_name, rpm_version=None):
    """Copy specific module name and version from repo1 to repo2.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param source: The source module to copy from.
    :param destination: The destination module to copy to.
    :param rpm_name: The name of target module.
    :param rpm_version: The version of target module.
    :returns: A :class: `pulp_smash.cli.CompletedProcess`.
    """
    return cli.Client(server_config).run(
        ' '.join([
            'pulp-admin rpm repo copy rpm --from-repo-id {}'.format(source),
            '--to-repo-id {}'.format(destination),
            '--str-eq=name={}'.format(rpm_name)
            if rpm_name is not None else '',
            '--str-eq=version={}'.format(rpm_version)
            if rpm_version is not None else '',
        ]).split()
    )


def _get_rpm_dependencies(server_config, repo_id, rpm_name):
    """Get a list of all required packages for a given RPM in repository.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param repo_id: The ID of repository which contains the module.
    :param rpm_name: The name of module to query with. It is assumed that
        there's no cycle in the dependecy relations; that is, a RPM cannot
        point itself as required package.
    """
    keyword = 'Requires:'
    res = []
    stack = [rpm_name]
    while len(stack) > 0:
        top = stack.pop()
        if top is not rpm_name:
            res.append(top)
        # Query parent modules for the current RPM `top`.
        completed_proc = cli.Client(server_config).run(
            'pulp-admin rpm repo content rpm --repo-id {0} --str-eq name={1} '
            '--fields=requires'.format(repo_id, top).split()
        )
        # Depth-First-Search for parent's dependencies.
        # E.g., 'walrus-0.71' <- 'whale' <- 'shark, stork' <- ''.
        # But 'walrus-5.21' <- '', i.e., it has no parent package.
        parent_modules = [
            line.split(keyword)[1].strip()
            for line in completed_proc.stdout.splitlines()
            if keyword in line and len(line.split(keyword)[1].strip()) > 0
        ]
        if len(parent_modules) == 0:
            continue
        stack.extend(parent_modules[0].split(', '))
    # Return [u'whale', u'stork', u'shark'] for 'walrus-0.71'.
    return res


def _clean_cache(server_config):
    """Utility function to execute `yum clean`."""
    cli.Client(server_config).run('yum clean all'.split())


def _query_rpm(server_config, rpm_name):
    """Utility function to query if a package is installed.

    :param pulp_smash.config.ServerConfig server_config: Information about the
        Pulp server being targeted.
    :param rpm_name: The name of target module.
    """
    return cli.Client(server_config).machine.session().run(
        'rpm -qa | grep "{}"'.format(rpm_name)
    )[1]


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
    global _REPO_ID  # pylint:disable=global-statement
    _REPO_ID = utils.uuid4()
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
                _count_langpacks(self.cfg, self.repo_id),
                0,
            )


class CopyAndPublishTwoVersionsRepoTestCase(CopyBaseTestCase):
    """Test whether a repo can copy two versions of RPMs and publish itself.

    This test case targets `Pulp Smash #311`_ and `Pulp # 1684`_.
    The test steps are as following:

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
    .. _Pulp # 1684: https://pulp.plan.io/issues/1684
    """

    @classmethod
    def setUpClass(cls):
        """Create two repositories and synchronize the 1st repo only."""
        super(CopyAndPublishTwoVersionsRepoTestCase, cls).setUpClass()
        _clean_cache(cls.cfg)
        # Retrieve all modules with multiple versions in the repo1.
        cls.rpm_dict = {
            key: value for (key, value)
            in _get_rpm_names_versions(cls.cfg, _REPO_ID).items()
            if len(value) > 1
        }
        assert len(cls.rpm_dict) > 0
        # Choose the first module with multiple versions.
        cls.rpm_name = list(cls.rpm_dict)[0]
        cls.rpm_dict.get(cls.rpm_name).sort()

    def test_01_copy_older_publish(self):
        """Copy a RPM with older version into repo2 and publish repo2."""
        # Choose the oldest version of the given RPM.
        rpm_version = self.rpm_dict.get(self.rpm_name, [None, None])[0]
        # Copy dependency packages of the chosen RPM.
        for rpm in _get_rpm_dependencies(self.cfg, _REPO_ID, self.rpm_name):
            _copy_repo(self.cfg, _REPO_ID, self.repo_id, rpm)
        self._copy_and_publish(self.rpm_name, rpm_version)

        # Setup the repo2 on the same host.
        cli.Client(self.cfg).run(
            'sudo yum-config-manager --add-repo {}'
            .format(urljoin('https://dev/pulp/repos/', self.repo_id)).split()
        )
        cli.Client(self.cfg).run('yum repolist enabled'.split())

        cli.Client(self.cfg).run(
            'dnf --disablerepo=* --enablerepo=dev_pulp_repos_{} list available'
            .format(self.repo_id).split()
        )

        # Execute `yum install` to deploy the RPM on the host.
        cli.Client(self.cfg).run(
            'sudo dnf install -y --nogpgcheck {}'.format(self.rpm_name).split()
        )
        self.assertIn(self.rpm_name, _query_rpm(self.cfg, self.rpm_name))

    def test_02_copy_newer_publish(self):
        """Copy a RPM with newer version into repo2 and publish repo2."""
        if selectors.bug_is_untestable(1684, self.cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1684')
        if self.rpm_name not in _query_rpm(self.cfg, self.rpm_name):
            self.skipTest('https://pulp.plan.io/issues/1684')
        # Choose the newest version of the given RPM.
        rpm_version = self.rpm_dict.get(self.rpm_name, [None, None])[1]
        self._copy_and_publish(self.rpm_name, rpm_version)
        # Execute `yum update` on the RPM.
        completed_proc = cli.Client(self.cfg).run(
            'sudo yum update {}'.format(self.rpm_name).split()
        )
        # Check if the update succeeds; it should have updates.
        self.assertNotIn('Nothing to do.', completed_proc.stdout.splitlines())

    def _copy_and_publish(self, rpm_name, rpm_version):
        """Copy the RPM with given name and version into 2nd repo and publish it.

        :param rpm_name: The name of target module.
        :param rpm_version: The version of target module.
        """
        # Copy the module from repo1 to repo2.
        _copy_repo(self.cfg, _REPO_ID, self.repo_id, rpm_name, rpm_version)
        # Search for the RPM's name/version in repo2's content.
        self._search_rpm(self.repo_id, rpm_name, rpm_version)
        # Publish repo2 and verify no errors.
        completed_proc = cli.Client(self.cfg).run(
            'pulp-admin rpm repo publish run --repo-id {}'
            .format(self.repo_id).split()
        )
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn(
                    'Task Failed', getattr(completed_proc, stream)
                )

    def _search_rpm(self, repo_id, rpm_name=None, rpm_version=None):
        """Search for a RPM in the repository with optional name or version.

        :param repo_id: A RPM repository ID.
        :param rpm_name: The name of target module.
        :param rpm_version: The version of target module.
        :returns: A :class: `pulp_smash.cli.CompletedProcess`.
        """
        completed_proc = cli.Client(self.cfg).run(
            ' '.join([
                'pulp-admin rpm repo content rpm --repo-id {}'.format(repo_id),
                '--str-eq name={}'.format(rpm_name)
                if rpm_name is not None else '',
                '--str-eq version={}'.format(rpm_version)
                if rpm_version is not None else ''
            ]).split()
        )
        if rpm_name is None:
            self.assertNotEqual('\x1b[0m', getattr(completed_proc, 'stdout'))
        else:
            self.assertIn(rpm_name, getattr(completed_proc, 'stdout'))
            # Check if the version is matched iif rpm's name is found.
            with self.subTest():
                self.assertIn(rpm_version, getattr(completed_proc, 'stdout'))

    @classmethod
    def tearDownClass(cls):
        """Delete the repositories and clean up orphans."""
        super(CopyAndPublishTwoVersionsRepoTestCase, cls).tearDownClass()
        # Delete the published repositories in yum.repos.d.
        cli.Client(cls.cfg).run(
            'sudo rm /etc/yum.repos.d/dev_pulp_repos_{}.repo'
            .format(cls.repo_id).split()
        )
        # Execute `yum remove` to delete the installed RPMs.
        # Add an error check to make the test robust.
        if cls.rpm_name not in _query_rpm(cls.cfg, cls.rpm_name):
            return
        cli.Client(cls.cfg).run(
            'sudo dnf remove -y {}'.format(cls.rpm_name).split()
        )
