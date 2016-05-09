# coding=utf-8
"""Test the `consumer`_ API endpoints.

.. _consumer:
    https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""
from __future__ import unicode_literals

from pulp_smash import api, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import CONSUMER_PATH, REPOSITORY_PATH
from pulp_smash.tests.rpm.api_v2.utils import gen_repo, gen_distributor


class BindConsumerTestCase(utils.BaseAPITestCase):
    """Show that one can `bind a consumer to a repository`_.

    .. _bind a consumer to a repository:
        https://pulp.readthedocs.io/en/latest/dev-guide/integration/rest-api/consumer/bind.html#bind-a-consumer-to-a-repository
    """

    @classmethod
    def setUpClass(cls):
        """Bind a consumer to a distributor.

        Do the following:

        1. Add a consumer.
        2. Add a repository.
        3. Add a distributor to the repository.
        4. Bind the consumer to the distributor.
        """
        super(BindConsumerTestCase, cls).setUpClass()

        # Steps 1–3
        client = api.Client(cls.cfg, api.json_handler)
        cls.consumer = client.post(CONSUMER_PATH, {'id': utils.uuid4()})
        repository = client.post(REPOSITORY_PATH, gen_repo())
        distributor = client.post(
            urljoin(repository['_href'], 'distributors/'),
            gen_distributor()
        )
        cls.resources.add(repository['_href'])

        # Step 4
        client.response_handler = api.safe_handler
        path = urljoin(CONSUMER_PATH, cls.consumer['consumer']['id'] + '/')
        path = urljoin(path, 'bindings/')
        cls.request = {
            'binding_config': {'B': 21},
            'distributor_id': distributor['id'],
            'notify_agent': False,
            'repo_id': distributor['repo_id'],
        }
        cls.response = client.post(path, cls.request)

    def test_status_code(self):
        """Assert the "bind" request returned an HTTP 200."""
        self.assertEqual(self.response.status_code, 200)

    def test_result(self):
        """Assert the distributor has a correct set of attributes."""
        result = self.response.json()['result']
        expect = {
            'binding_config': result['binding_config'],
            'consumer_id': self.consumer['consumer']['id'],
            'distributor_id': result['distributor_id'],
            'repo_id': result['repo_id'],
        }
        for key, value in expect.items():
            with self.subTest(key=key):
                self.assertEqual(result[key], value)
