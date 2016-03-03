# coding=utf-8
"""Test the `consumer`_ API endpoints.

.. _consumer:
    https://pulp.readthedocs.org/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""

from __future__ import unicode_literals

from urlparse import urljoin

from pulp_smash.api import Client, json_handler
from pulp_smash.constants import CONSUMER_PATH, REPOSITORY_PATH
from pulp_smash.tests.rpm.api_v2.utils import gen_repo, gen_distributor
from pulp_smash.utils import BaseAPITestCase, uuid4


class TestBindTestCase(BaseAPITestCase):

    def _add_consumer(self, client):
        """Add a new consumer and return it."""
        body = {
            'id': uuid4()
        }
        url = CONSUMER_PATH
        return client.post(url, body)

    def _add_repository(self, client):
        """Add a new repository and return it."""
        body = gen_repo()
        url = REPOSITORY_PATH
        repository = client.post(url, body)
        self.resources.add(repository['_href'])
        return repository

    def _add_distributor(self, client, repository):
        """Add a distributor to the specified repository and return it."""
        body = gen_distributor()
        url = urljoin(repository['_href'], 'distributors/')
        return client.post(url, body)

    def _bind(self, client, consumer, distributor):
        """Bind the consumer to the distributor and return the both the
        POST body and the http response.
        """
        body = {
            'repo_id': distributor['repo_id'],
            'distributor_id': distributor['id'],
            'notify_agent': False,
            'binding_config': {'B': 21}
        }
        path = '/'.join((consumer['consumer']['id'], 'bindings/'))
        url = urljoin(CONSUMER_PATH, path)
        return body, client.post(url, body)

    def test_bind_succeeded(self):
        """Test binding a consumer to a distributor:
            1. add a consumer.
            2. add a repository.
            3. add a distributor to the repository.
            4. bind the consumer to the distributor.

            Assert:
            1. http code = 200.
            2. the created binding has properties passed in the POST body.
        """
        client = Client(self.cfg, json_handler)
        consumer = self._add_consumer(client)
        repository = self._add_repository(client)
        distributor = self._add_distributor(client, repository)

        # test
        client = Client(self.cfg)
        body, response = self._bind(client, consumer, distributor)

        # validation
        binding = response.json()['result']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(binding['consumer_id'], consumer['consumer']['id'])
        self.assertEqual(binding['distributor_id'], body['distributor_id'])
        self.assertEqual(binding['binding_config'], body['binding_config'])
        self.assertEqual(binding['repo_id'], body['repo_id'])
