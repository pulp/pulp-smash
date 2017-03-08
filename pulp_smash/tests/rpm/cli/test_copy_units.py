# coding=utf-8
"""Tests that copy units from one repository to another."""
import os
import subprocess
import unittest
from io import StringIO
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import cli, config, constants, selectors, utils
from pulp_smash.tests.rpm.cli.utils import count_langpacks
from pulp_smash.tests.rpm.utils import (
    check_issue_2277,
    check_issue_2620,
    set_up_module,
)
from pulp_smash.utils import is_root

_REPO_ID = utils.uuid4()
"""The ID of the repository created by ``setUpModule``."""


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
        .format(_REPO_ID, constants.RPM_SIGNED_FEED_URL).split()
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


class UtilsMixin(object):  # pylint:disable=too-few-public-methods
    """A mixin providing useful tools to unittest subclasses.

    Any class inheriting from this mixin must also inherit from
    ``unittest.TestCase`` or a compatible clone.
    """

    def create_repo(self, cfg):
        """Create a repository and schedule it for deletion.

        :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system on which
            to create a repository.
        :return: The repository's ID.
        """
        repo_id = utils.uuid4()
        client = cli.Client(cfg)
        client.run(
            'pulp-admin rpm repo create --repo-id {}'.format(repo_id).split()
        )
        self.addCleanup(
            client.run,
            'pulp-admin rpm repo delete --repo-id {}'.format(repo_id).split()
        )
        return repo_id


def gen_yum_config_file(cfg, repositoryid, **kwargs):
    """Generate a yum configuration file and write it to ``/etc/yum.repos.d/``.

    Generate a yum configuration file containing a single repository section,
    and write it to ``/etc/yum.repos.d/{repositoryid}.repo``.

    :param pulp_smash.config.PulpSmashConfig cfg: The system on which to create
        a yum configuration file.
    :param repositoryid: The section's ``repositoryid``. Used when naming the
        configuration file and populating the brackets at the head of the file.
        For details, see yum.conf(5).
    :param kwargs: Section options. Each kwarg corresponds to one option. For
        details, see yum.conf(5).
    :returns: The path to the yum configuration file.
    """
    path = os.path.join('/etc/yum.repos.d/', repositoryid + '.repo')
    with StringIO() as section:
        section.write('[{}]\n'.format(repositoryid))
        for key, value in kwargs.items():
            section.write('{}: {}\n'.format(key, value))
        cli.Client(cfg).machine.session().run(
            'echo "{}" | {}tee {} > /dev/null'
            .format(section.getvalue(), '' if is_root(cfg) else 'sudo ', path)
        )
    return path


def _get_rpm_names_versions(server_config, repo_id):
    """Get a dict of repo's RPMs with names as keys, mapping to version lists.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp deployment being targeted.
    :param repo_id: A RPM repository ID.
    :returns: The name and versions of each package in the repository, with the
        versions sorted in ascending order. For example: ``{'walrus': ['0.71',
        '5.21']}``.
    """
    keyword = 'Filename:'
    completed_proc = cli.Client(server_config).run(
        'pulp-admin rpm repo content rpm --repo-id {}'.format(repo_id).split()
    )
    rpms = {}
    for line in completed_proc.stdout.splitlines():
        if keyword not in line:
            continue
        # e.g. 'Filename: my-walrus-0.71-1.noarch.rpm ' → ['my-walrus', '0.71']
        filename_parts = line.lstrip(keyword).strip().split('-')[:-1]
        name = '-'.join(filename_parts[:-1])
        version = filename_parts[-1]
        rpms.setdefault(name, []).append(version)
    for rpm in rpms:
        rpms[rpm] = sorted(rpms[rpm], key=Version)
    return rpms


class CopyTestCase(UtilsMixin, unittest.TestCase):
    """Copy a "chimpanzee" unit from one repository to another.

    This test case verifies that it is possible to use the ``pulp-admin rpm
    repo copy`` command to copy a single unit from one repository to another.
    """

    def test_all(self):
        """Copy a "chimpanzee" unit from one repository to another.

        Verify that only the "chimpanzee" unit is in the target repository.
        """
        cfg = config.get_config()
        if check_issue_2620(cfg):
            self.skipTest('https://pulp.plan.io/issues/2620')
        repo_id = self.create_repo(cfg)
        cli.Client(cfg).run(
            'pulp-admin rpm repo copy rpm --from-repo-id {} --to-repo-id {} '
            '--str-eq name=chimpanzee'.format(_REPO_ID, repo_id).split()
        )
        rpms = _get_rpm_names_versions(cfg, repo_id)
        self.assertEqual(list(rpms.keys()), ['chimpanzee'])
        self.assertEqual(len(rpms['chimpanzee']), 1, rpms)


class CopyRecursiveTestCase(UtilsMixin, unittest.TestCase):
    """Recursively copy a "chimpanzee" unit from one repository to another.

    This test case verifies that it is possible to use the ``pulp-admin rpm
    repo copy`` command to recursively copy units from one repository to
    another. See `Pulp Smash #107`_.

    .. _Pulp Smash #107: https://github.com/PulpQE/pulp-smash/issues/107
    """

    def test_all(self):
        """Recursively copy a "chimpanzee" unit from one repository to another.

        "chimpanzee" depends on "walrus," and there are multiple versions of
        "walrus" in the source repository. Verify that one "walrus" unit has
        been copied to the target repository, and that the newer one has been
        copied.
        """
        cfg = config.get_config()
        if check_issue_2620(cfg):
            self.skipTest('https://pulp.plan.io/issues/2620')
        repo_id = self.create_repo(cfg)
        cli.Client(cfg).run(
            'pulp-admin rpm repo copy rpm --from-repo-id {} --to-repo-id {} '
            '--str-eq name=chimpanzee --recursive'
            .format(_REPO_ID, repo_id).split()
        )

        # Verify only one "walrus" unit has been copied
        dst_rpms = _get_rpm_names_versions(cfg, repo_id)
        self.assertIn('walrus', dst_rpms)
        self.assertEqual(len(dst_rpms['walrus']), 1, dst_rpms)

        # Verify the version of the "walrus" unit
        src_rpms = _get_rpm_names_versions(cfg, _REPO_ID)
        self.assertEqual(src_rpms['walrus'][-1], dst_rpms['walrus'][0])


class CopyLangpacksTestCase(UtilsMixin, unittest.TestCase):
    """Copy langpacks from one repository to another.

    This test case verifies that it is possible to use the ``pulp-admin rpm
    repo copy langpacks`` command to copy langpacks from one repository to
    another. See `Pulp Smash #255`_.

    .. _Pulp Smash #255: https://github.com/PulpQE/pulp-smash/issues/255
    """

    def test_all(self):
        """Copy langpacks from one repository to another.

        Assert that:

        * ``pulp-admin`` does not produce any errors.
        * A non-zero number of langpacks are present in the target repository.
        """
        cfg = config.get_config()
        if selectors.bug_is_untestable(1367, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/1367')
        repo_id = self.create_repo(cfg)
        completed_proc = cli.Client(cfg).run(
            'pulp-admin rpm repo copy langpacks --from-repo-id {} '
            '--to-repo-id {}'.format(_REPO_ID, repo_id).split()
        )
        with self.subTest(comment='verify copy command stdout'):
            self.assertNotIn('Task Failed', completed_proc.stdout)
        with self.subTest(comment='verify langpack count in repo'):
            self.assertGreater(count_langpacks(cfg, repo_id), 0)


class UpdateRpmTestCase(UtilsMixin, unittest.TestCase):
    """Update an RPM in a repository and on a host.

    Do the following:

    1. Create two repositories. Populate the first, and leave the second empty.
    2. Pick an RPM with at least two versions.
    3. Copy the older version of the RPM from the first repository to the
       second, and publish the second repository.
    4. Pick a host system capable of installing RPMs. (By default, this is the
       system hosting Pulp.) Make it add the second repository as a source of
       packages, and make it install the RPM.
    5. Copy the newer version of the RPM from the first repository to the
       second, and publish the second repository.
    6. Make the host install the newer RPM with ``yum update rpm_name``, or a
       similar command.

    This test case targets `Pulp Smash #311
    <https://github.com/PulpQE/pulp-smash/issues/311>`_.
    """

    def test_all(self):
        """Update an RPM in a repository and on a host."""
        cfg = config.get_config()
        if check_issue_2277(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2277')
        if check_issue_2620(cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/2620')
        client = cli.Client(cfg)
        pkg_mgr = cli.PackageManager(cfg)
        sudo = '' if is_root(cfg) else 'sudo '

        # Create the second repository.
        repo_id = self.create_repo(cfg)

        # Pick an RPM with two versions.
        rpm_name = 'walrus'
        rpm_versions = _get_rpm_names_versions(cfg, _REPO_ID)[rpm_name]

        # Copy the older RPM to the second repository, and publish it.
        self._copy_and_publish(cfg, rpm_name, rpm_versions[0], repo_id)

        # Install the RPM on a host.
        repo_path = gen_yum_config_file(
            cfg,
            baseurl=urljoin(cfg.base_url, 'pulp/repos/' + repo_id),
            enabled=1,
            gpgcheck=0,
            metadata_expire=0,  # force metadata to load every time
            repositoryid=repo_id,
            sslverify='yes' if cfg.verify else 'no',
        )
        self.addCleanup(
            client.run,
            '{}rm {}'.format(sudo, repo_path).split()
        )
        pkg_mgr.install(rpm_name)
        self.addCleanup(pkg_mgr.uninstall, rpm_name)
        client.run(['rpm', '-q', rpm_name])

        # Copy the newer RPM to the second repository, and publish it.
        self._copy_and_publish(cfg, rpm_name, rpm_versions[1], repo_id)

        # Update the installed RPM on the host.
        proc = pkg_mgr.upgrade(rpm_name)
        self.assertNotIn('Nothing to do.', proc.stdout)

    def _copy_and_publish(self, cfg, rpm_name, rpm_version, repo_id):
        """Copy an RPM from repository ``_REPO_ID`` to the given repository.

        :param rpm_name: The name of the RPM to copy.
        :param rpm_version: The version of the RPM to copy.
        :param repo_id: The repository to which the RPM is copied.
        """
        client = cli.Client(cfg)

        # Copy the package and its dependencies to the new repo
        client.run(
            'pulp-admin rpm repo copy rpm --from-repo-id {} --to-repo-id {} '
            '--str-eq=name={} --str-eq=version={} --recursive'
            .format(_REPO_ID, repo_id, rpm_name, rpm_version).split()
        )

        # Search for the RPM's name/version in repo2's content.
        result = client.run(
            'pulp-admin rpm repo content rpm --repo-id {} --str-eq name={} '
            '--str-eq version={}'
            .format(repo_id, rpm_name, rpm_version).split()
        )
        with self.subTest(comment='rpm name present'):
            self.assertIn(rpm_name, result.stdout)
        with self.subTest(comment='rpm version present'):
            self.assertIn(rpm_version, result.stdout)

        # Publish repo2 and verify no errors.
        proc = client.run(
            'pulp-admin rpm repo publish run --repo-id {}'
            .format(repo_id).split()
        )
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn('Task Failed', getattr(proc, stream))
