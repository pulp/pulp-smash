# coding=utf-8
"""Utility functions for Docker API tests."""
from urllib.parse import urlsplit, urlunsplit

from pulp_smash import api, cli, utils
from pulp_smash.tests.pulp2.constants import REPOSITORY_PATH
from pulp_smash.tests.pulp2.docker.utils import get_upstream_name


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

    def create_repo(self, cfg, enable_v1, enable_v2, feed):
        """Create, sync and publish a repository.

        Specifically do the following:

        1. Create, sync and publish a Docker repository.
        2. Make Crane immediately re-read the metadata files published by
           Pulp.(Restart Apache)

        :param pulp_smash.config.PulpSmashConfig cfg: Information about a Pulp
            deployment.
        :param enable_v1: A boolean. Either ``True`` or ``False``.
        :param enable_v2: A boolean. Either ``True`` or ``False``.
        :param feed: A value for the docker importer's ``feed`` option.
        :returns: A detailed dict of information about the repository.
        """
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config'].update({
            'enable_v1': enable_v1,
            'enable_v2': enable_v2,
            'feed': feed,
            'upstream_name': get_upstream_name(cfg),
        })
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(
            repo['_href'],
            params={'details': True}
        )
        utils.sync_repo(cfg, repo)
        utils.publish_repo(cfg, repo)

        # Make Crane re-read metadata. (Now!)
        cli.GlobalServiceManager(cfg).restart(('httpd',))

        return repo
