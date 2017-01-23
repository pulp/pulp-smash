# coding=utf-8
"""Tests that perform searches."""
import unittest

from pulp_smash import cli, config, utils
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import


class SearchReposWithFiltersTestCase(unittest.TestCase):
    """Search for repositories, and use filters to limit matches.

    This test case targets `Pulp #1784`_ and `Pulp Smash #184`_. The
    `repository search`_ documentation describes the CLI search syntax.

    .. _Pulp #1784:  https://pulp.plan.io/issues/1784
    .. _Pulp Smash #184: https://github.com/PulpQE/pulp-smash/issues/184
    .. _repository search:
        http://docs.pulpproject.org/en/latest/user-guide/consumer-client/repositories.html
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        cfg = config.get_config()
        utils.pulp_admin_login(cfg)
        cls.client = cli.Client(cfg)
        cls.repo_id = utils.uuid4()
        cls.client.run(
            'pulp-admin rpm repo create --repo-id {}'
            .format(cls.repo_id).split()
        )

    @staticmethod
    def gen_commands(repo_id):
        """Generate the commands used by the test methods.

        Commands with the following filters are returned::

            --filters {'id':'…'}
            --filters {'repo_id':'…'}
            --str-eq id=…
            --str-eq repo_id=…
        """
        filter_templates = (
            '--filters {{"id":"{0}"}}',
            '--filters {{"repo_id":"{0}"}}',
            '--str-eq id={0}',
            '--str-eq repo_id={0}',
        )
        filters = (filter_t.format(repo_id) for filter_t in filter_templates)
        return ('pulp-admin rpm repo search ' + filter_ for filter_ in filters)

    def test_positive_searches(self):
        """Search for the repository with a matching repository ID."""
        for command in self.gen_commands(self.repo_id):
            with self.subTest(command=command):
                result = self.client.run(command.split())
                self.assertEqual(result.stdout.count('Id:'), 1, result)

    def test_negative_searches(self):
        """Search for the repository with a non-matching repository ID."""
        for command in self.gen_commands(utils.uuid4()):
            with self.subTest(command=command):
                result = self.client.run(command.split())
                self.assertEqual(result.stdout.count('Id:'), 0, result)

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
