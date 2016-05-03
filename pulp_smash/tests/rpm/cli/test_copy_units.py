# coding=utf-8
"""Tests that copy units from one repository to another."""
from __future__ import unicode_literals

import inspect
import subprocess

import unittest2

from pulp_smash import cli, config, constants, selectors, utils
from pulp_smash.tests.rpm.utils import set_up_module

_REPO_ID = None
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
