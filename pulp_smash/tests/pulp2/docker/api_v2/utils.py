# coding=utf-8
"""Utility functions for Docker API tests."""
from urllib.parse import urlsplit, urlunsplit

from pulp_smash import api, cli, utils
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import publish_repo, sync_repo


def gen_repo():
    """Return a semi-random dict that used for creating a Docker repo."""
    return {
        'id': utils.uuid4(),
        'importer_config': {},
        'importer_type_id': 'docker_importer',
        'notes': {'_repo-type': 'docker-repo'},
    }


def gen_distributor():
    """Return a semi-random dict for use in creating a Docker distributor."""
    return {
        'auto_publish': False,
        'distributor_config': {},
        'distributor_id': utils.uuid4(),
        'distributor_type_id': 'docker_distributor_web',
    }


class SyncPublishMixin():
    """Tools for test cases that sync and publish Docker repositories.

    This class must be mixed in to a class that inherits from
    ``unittest.TestCase``.
    """

    @staticmethod
    def adjust_url(url):
        """Return a URL that can be used for talking with Crane.

        The URL returned is the same as ``url``, except that the scheme is set
        to HTTP, and the port is set to (or replaced by) 5000.

        :param url: A string, such as ``https://pulp.example.com/foo``.
        :returns: A string, such as ``http://pulp.example.com:5000/foo``.
        """
        parse_result = urlsplit(url)
        netloc = parse_result[1].partition(':')[0] + ':5000'
        return urlunsplit(('http', netloc) + parse_result[2:])

    @staticmethod
    def make_crane_client(cfg):
        """Make an API client for talking with Crane.

        Create an API client for talking to Crane. The client returned by this
        method is similar to the following ``client``:

        >>> client = api.Client(cfg, api.json_handler)

        However:

        * The client's base URL is adjusted as described by :meth:`adjust_url`.
        * The client will send an ``accept:application/json`` header with each
          request.

        :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
            deployment.
        :returns: An API client for talking with Crane.
        :rtype: pulp_smash.api.Client
        """
        client = api.Client(
            cfg,
            api.json_handler,
            {'headers': {'accept': 'application/json'}},
        )
        client.request_kwargs['url'] = SyncPublishMixin.adjust_url(
            client.request_kwargs['url']
        )
        return client

    def create_sync_publish_repo(
            self,
            cfg,
            importer_config,
            distributors=None):
        """Create, sync and publish a repository.

        Specifically do the following:

        1. Create a repository and schedule it for deletion.
        2. Sync and publish the repository.
        3. Make Crane immediately re-read the metadata files published by Pulp.
           (Restart Apache)

        :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
            deployment.
        :param importer_config: An importer configuration to pass when creating
            the repository. For example: ``{'feed': '…'}``.
        :param distributors: Distributor configurations to pass when creating
            the repository. If no value is passed, one will be generated.
        :returns: A detailed dict of information about the repository.
        """
        # create repository
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'].update(importer_config)
        if distributors is None:
            body['distributors'] = [gen_distributor()]
        else:
            body['distributors'] = distributors
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])

        # Sync, publish, and re-read metadata.
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)
        cli.GlobalServiceManager(cfg).restart(('httpd',))
        return client.get(repo['_href'], params={'details': True})
