# coding=utf-8
"""Test the `consumer`_ API endpoints.

.. _consumer:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.constants import CONSUMERS_PATH, REPOSITORY_PATH
from pulp_smash.tests.rpm.api_v2.utils import gen_repo, gen_distributor


class BindConsumerTestCase(unittest.TestCase):
    """Show that one can `bind a consumer to a repository`_.

    .. _bind a consumer to a repository:
        https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/bind.html#bind-a-consumer-to-a-repository
    """

    def test_all(self):
        """Bind a consumer to a distributor.

        Do the following:

        1. Create a repository with a distributor.
        2. Create a consumer.
        3. Bind the consumer to the distributor.

        Assert that:

        * The response has an HTTP 200 status code.
        * The response body contains the correct values.
        """
        cfg = config.get_config()
        client = api.Client(cfg)

        # Steps 1–2
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body).json()
        self.addCleanup(client.delete, repo['_href'])
        consumer = client.post(CONSUMERS_PATH, {'id': utils.uuid4()}).json()
        self.addCleanup(client.delete, consumer['consumer']['_href'])

        # Step 3
        repo = client.get(repo['_href'], params={'details': True}).json()
        path = urljoin(CONSUMERS_PATH, consumer['consumer']['id'] + '/')
        path = urljoin(path, 'bindings/')
        body = {
            'binding_config': {'B': 21},
            'distributor_id': repo['distributors'][0]['id'],
            'notify_agent': False,
            'repo_id': repo['id'],
        }
        response = client.post(path, body)

        with self.subTest(comment='check response status code'):
            self.assertEqual(response.status_code, 200)

        result = response.json()['result']
        with self.subTest(comment='check response body'):
            self.assertEqual(result['binding_config'], body['binding_config'])
            self.assertEqual(result['consumer_id'], consumer['consumer']['id'])
            self.assertEqual(result['distributor_id'], body['distributor_id'])
            self.assertEqual(result['repo_id'], body['repo_id'])
