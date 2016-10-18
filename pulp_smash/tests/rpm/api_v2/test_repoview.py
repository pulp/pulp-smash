# coding=utf-8
"""Tests that exercise Pulp's repoview feature.

For more information, see:

* `Pulp #189 <https://pulp.plan.io/issues/189>`_: "Repoview-like functionality
  for browsing repositories via the web interface"
* Yum Plugins → Yum Distributor → `Optional Configuration Parameters
  <http://docs.pulpproject.org/plugins/pulp_rpm/tech-reference/yum-plugins.html#optional-configuration-parameters>`_
"""
import unittest
from urllib.parse import urljoin

from packaging.version import Version

from pulp_smash import api, config, constants, selectors, utils
from pulp_smash.tests.rpm.utils import set_up_module as setUpModule  # noqa pylint:disable=unused-import
from pulp_smash.tests.rpm.api_v2.utils import gen_distributor, gen_repo


class RepoviewTestCase(unittest.TestCase):
    """Publish a repository with the repoview feature on and off.

    Do the following:

    1. Create an RPM repository, and add some content to it.
    2. Publish the repository. Get ``/pulp/repos/{rel_url}/``, and verify that
       no redirects occur.
    3. Publish the repository with the ``repoview`` and ``generate_sqlite``
       options set to true. Get ``/pulp/repos/{rel_url}/``, and verify that a
       redirect to ``/pulp/repos/{rel_url}/repoview/index.html`` occurs.
    4. Repeat step 2.
    """

    def test_all(self):
        """Publish a repository with the repoview feature on and off."""
        cfg = config.get_config()
        if cfg.version < Version('2.9'):
            self.skipTest('https://pulp.plan.io/issues/189')

        # Create a repo, and add content
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo_href = client.post(constants.REPOSITORY_PATH, body)['_href']
        self.addCleanup(client.delete, repo_href)
        rpm = utils.http_get(constants.RPM_UNSIGNED_URL)
        utils.upload_import_unit(cfg, rpm, 'rpm', repo_href)

        # Gather some facts about the repo distributor
        dist = client.get(urljoin(repo_href, 'distributors/'))[0]
        dist_url = urljoin('/pulp/repos/', dist['config']['relative_url'])

        # Publish the repo
        client.response_handler = api.safe_handler
        client.post(urljoin(repo_href, 'actions/publish/'), {'id': dist['id']})
        response = client.get(dist_url)
        with self.subTest(comment='first publish'):
            self.assertEqual(len(response.history), 0, response.history)

        # Publish the repo a second time
        client.post(
            urljoin(repo_href, 'actions/publish/'),
            {'id': dist['id'], 'override_config': {
                'generate_sqlite': True,
                'repoview': True,
            }},
        )
        response = client.get(dist_url)
        with self.subTest(comment='second publish'):
            self.assertEqual(len(response.history), 1, response.history)
            self.assertEqual(
                response.request.url,
                urljoin(response.history[0].request.url, 'repoview/index.html')
            )

        # Publish the repo a third time
        if selectors.bug_is_untestable(2349, cfg.version):
            self.skipTest('https://pulp.plan.io/issues/2349')
        client.post(urljoin(repo_href, 'actions/publish/'), {'id': dist['id']})
        response = client.get(dist_url)
        with self.subTest(comment='third publish'):
            self.assertEqual(len(response.history), 0, response.history)
