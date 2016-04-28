# coding=utf-8
"""Test CRUD for Docker repositories.

This module contains tests for creating Docker repositories. It is intended to
also contain read, update, and delete tests.
"""
from __future__ import unicode_literals

import unittest2

from packaging.version import Version

from pulp_smash import api, config, utils
from pulp_smash.compat import urljoin
from pulp_smash.constants import REPOSITORY_PATH
from pulp_smash.tests.docker.api_v2.utils import gen_repo
from pulp_smash.tests.docker.utils import set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Skip tests on Pulp versions lower than 2.8."""
    set_up_module()
    if config.get_config().version < Version('2.8'):
        raise unittest2.SkipTest('These tests require at least Pulp 2.8.')


def _gen_distributor():
    """Return a semi-random dict for use in creating a docker distributor."""
    return {
        'auto_publish': False,
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'docker_distributor_web',
        'distributor_config': {
            'http': True,
            'https': True,
        },
    }


class CrudTestCase(utils.BaseAPICrudTestCase):
    """CRUD a minimal Docker repository."""

    @staticmethod
    def create_body():
        """Return a dict for creating a repository."""
        return gen_repo()

    @staticmethod
    def update_body():
        """Return a dict for creating a repository."""
        return {'delta': {'display_name': utils.uuid4()}}


class CrudWithFeedTestCase(CrudTestCase):
    """CRUD a Docker repository with a feed."""

    @staticmethod
    def create_body():
        """Return a dict, with a feed, for creating a repository."""
        body = CrudTestCase.create_body()
        body['importer_config'] = {'feed': 'http://' + utils.uuid4()}
        return body


class UpdateTestCase(utils.BaseAPITestCase):
    """Show it is possible to update a distributor for a docker repository."""

    @classmethod
    def setUpClass(cls):
        """Create a docker repo with a distributor, and update the distributor.

        Do the following:

        1. Create a docker repository and add a distributor.
        2. Update the distributor. Use the distributor's href in the request.
        3. Update the distributor. Use the repository's href in the request,
           and ensure the distributor is updated by packing certain data in the
           request body.
        """
        super(UpdateTestCase, cls).setUpClass()
        cls.sent_ids = tuple(('test/' + utils.uuid4() for _ in range(2)))
        cls.responses = {}

        # Create a repository and a distributor
        client = api.Client(cls.cfg)
        repo = client.post(REPOSITORY_PATH, gen_repo()).json()
        cls.resources.add(repo['_href'])
        cls.responses['add distributor'] = client.post(
            urljoin(repo['_href'], 'distributors/'),
            _gen_distributor(),
        )
        distributor = cls.responses['add distributor'].json()

        # Update the distributor
        cls.responses['first update'] = client.put(
            distributor['_href'],
            {'distributor_config': {'repo_registry_id': cls.sent_ids[0]}},
        )
        cls.responses['first read'] = client.get(distributor['_href'])

        # Update the distributor again, from repo this time
        cls.responses['second update'] = client.put(
            repo['_href'],
            {'distributor_configs': {distributor['id']: {
                'repo_registry_id': cls.sent_ids[1],
            }}},
        )
        cls.responses['second read'] = client.get(distributor['_href'])

    def test_status_codes(self):
        """Verify each of the server's responses has a correct status code."""
        for step, code in (
                ('add distributor', 201),
                ('first update', 202),
                ('first read', 200),
                ('second update', 202),
                ('second read', 200),
        ):
            with self.subTest(step=step):
                self.assertEqual(self.responses[step].status_code, code)

    def test_update_accepted(self):
        """Verify the information sent to the server can be read back."""
        read_ids = [
            self.responses[response].json()['config']['repo_registry_id']
            for response in ('first read', 'second read')
        ]
        for i, (sent_id, read_id) in enumerate(zip(self.sent_ids, read_ids)):
            with self.subTest(i=i):
                self.assertEqual(sent_id, read_id)
