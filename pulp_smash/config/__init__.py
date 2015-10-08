# coding=utf-8
"""Tools for managing information about test systems.

Pulp Smash needs to know what servers it can talk to and how to talk to those
systems. For example, it needs to know the protocol, hostname and port of a
Pulp server (e.g. 'https://example.com:250') and how to authenticate with that
server. :class:`pulp_smash.config.ServerConfig` eases the task of managing that
information.

"""
from __future__ import unicode_literals

from pulp_smash.config.base import ConfigSection
from pulp_smash.config.mixins import AuthMixin


# `get_config` uses this as a cache. It is intentionally a global. This design
# lets us do interesting things like flush the cache at run time or completely
# avoid a config file by fetching values from the UI.
_CONFIG = None


def get_config():
    """Return a copy of the global ``ServerConfig`` object.

    This method makes use of a cache. If the cache is empty, the configuration
    file is parsed and the cache is populated. Otherwise, a copy of the cached
    configuration object is returned.

    :returns: A copy of the global ``ServerConfig`` object.
    :rtype: pulp_smash.config.ServerConfig

    """
    global _CONFIG  # pylint:disable=global-statement
    if _CONFIG is None:
        _CONFIG = ServerConfig.read()
    return ServerConfig(**_CONFIG.copy())


class ServerConfig(AuthMixin, ConfigSection):
    """A dict-like object that stores facts about a single server.

    This class inherits most of its functionality from its parent classes,
    especially :class:`pulp_smash.config.base.ConfigSection`.

    :param base_url: A string that consists of a URL protocol, hostname and
        port. It must not have a trailing slash. Here are some valid examples::

            http://example.com
            https://example.com:250

        Here are some invalid examples::

            example.com
            http://example.com/

    """
    _xdg_config_dir = 'pulp_smash'

    def __init__(self, base_url, *args, **kwargs):
        super(ServerConfig, self).__init__(base_url=base_url, *args, **kwargs)
