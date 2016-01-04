# coding=utf-8
"""Tools for managing information about test systems.

Pulp Smash needs to know what servers it can talk to and how to talk to those
systems. For example, it needs to know the protocol, hostname and port of a
Pulp server (e.g. 'https://example.com:250') and how to authenticate with that
server. :class:`pulp_smash.config.ServerConfig` eases the task of managing that
information.
"""
from __future__ import unicode_literals

import json
import os
from copy import deepcopy
from threading import Lock

from packaging.version import Version
from xdg import BaseDirectory


# `get_config` uses this as a cache. It is intentionally a global. This design
# lets us do interesting things like flush the cache at run time or completely
# avoid a config file by fetching values from the UI.
_CONFIG = None


def _public_attrs(obj):
    """Return a copy of the public elements in ``vars(obj)``."""
    return {
        key: val for key, val in vars(obj).copy().items()
        if not key.startswith('_')
    }


def get_config():
    """Return a copy of the global ``ServerConfig`` object.

    This method makes use of a cache. If the cache is empty, the configuration
    file is parsed and the cache is populated. Otherwise, a copy of the cached
    configuration object is returned.

    :returns: A copy of the global server configuration object.
    :rtype: pulp_smash.config.ServerConfig
    """
    global _CONFIG  # pylint:disable=global-statement
    if _CONFIG is None:
        _CONFIG = ServerConfig().read()
    return deepcopy(_CONFIG)


class ConfigFileNotFoundError(Exception):
    """Indicates that the requested XDG configuration file cannot be found."""


class ServerConfig(object):
    """Facts about a server, plus methods for manipulating those facts.

    This object stores a set of facts that are used when communicating with a
    Pulp server. A typical usage of this object is as follows:

    >>> import requests
    >>> from pulp_smash.config import ServerConfig
    >>> cfg = ServerConfig(
    ...     base_url='https://pulp.example.com',
    ...     auth=('username', 'password'),
    ...     verify=False,  # Disable SSL verification
    ...     version='2.7.5',
    ... )
    >>> response = requests.post(
    ...     cfg.base_url + '/pulp/api/v2/actions/login/',
    ...     **cfg.get_requests_kwargs()
    ... )

    One can also :meth:`save` a ``ServerConfig`` out to a file, :meth:`read`
    one back and more. By way of example, assume that a file with the following
    contents exists on the filesystem::

        {
          "default": {"base_url": "example.com", "auth": ["alice", "hackme"]},
          "alternate": {"base_url": "example.org", "auth": ["bob", "hackme"]},
        }

    The two top-level sections can be read like so:

    >>> from pulp_smash.config import ServerConfig
    >>> 'example.com' == ServerConfig().read('default').base_url
    >>> 'example.org' == ServerConfig().read('alternate').base_url

    By default, :meth:`read` reads the "default" section. As a result, this
    holds true:

    >>> from pulp_smash.config import ServerConfig
    >>> ServerConfig().read() == ServerConfig().read('default')
    >>> ServerConfig().read() != ServerConfig().read('alternate')

    All methods dealing with files obey the `XDG Base Directory Specification
    <http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html>`_.
    Please read the specification for insight into the logic of those methods.

    In addition, the file-facing methods respect the ``PULP_SMASH_CONFIG_FILE``
    environment variable. By default, the methods work with a file named
    ``settings.json``, but the environment variable overrides that default. If
    set, the environment variable should be a file name like ``settings2.json``
    (or a relative path), *not* an absolute path.

    :param base_url: A string. A protocol, hostname and optionally a port. For
        example, ``'http://example.com:250'``. Do not append a trailing slash.
    :param auth: A two-tuple. Credentials to use when communicating with the
        server. For example: ``('username', 'password')``.
    :param verify: A boolean. Should SSL be verified when communicating with
        the server?
    """

    # Used to lock access to the configuration file when performing destructive
    # operations, such as saving.
    _file_lock = Lock()

    def __init__(self, base_url=None, auth=None, verify=None, version=None):  # noqa
        self.base_url = base_url
        self.auth = auth
        self.verify = verify
        if version is None:
            self.version = Version('1!0')
        else:
            self.version = Version(version)

        self._section = 'default'
        self._xdg_config_file = os.environ.get(
            'PULP_SMASH_CONFIG_FILE',
            'settings.json'
        )
        self._xdg_config_dir = 'pulp_smash'

    def __repr__(self):  # noqa
        attrs = _public_attrs(self)
        attrs['version'] = type('')(attrs['version'])
        str_kwargs = ', '.join(
            '{}={}'.format(key, repr(value)) for key, value in attrs.items()
        )
        return '{}({})'.format(type(self).__name__, str_kwargs)

    def save(self, section=None, xdg_config_file=None, xdg_config_dir=None):
        """Save ``self`` as a top-level section of a configuration file.

        This method is thread-safe.

        :param section: A string. An identifier for the current configuration.
            If no top-level section named ``section`` exists in the
            configuration file, one is created. Otherwise, it is replaced.
        :param xdg_config_file: A string. The name of the file to manipulate.
        :param xdg_config_dir: A string. The XDG configuration directory in
            which the configuration file resides.
        :returns: Nothing.
        """
        # What will we write out?
        if section is None:
            section = self._section
        attrs = _public_attrs(self)
        attrs['version'] = type('')(attrs['version'])

        # What file is being manipulated?
        if xdg_config_file is None:
            xdg_config_file = self._xdg_config_file
        if xdg_config_dir is None:
            xdg_config_dir = self._xdg_config_dir
        path = os.path.join(
            BaseDirectory.save_config_path(xdg_config_dir),
            xdg_config_file
        )

        # Lock, write, unlock.
        self._file_lock.acquire()
        try:
            try:
                with open(path) as config_file:
                    config = json.load(config_file)
            except IOError:
                config = {}
            config[section] = attrs
            with open(path, 'w') as config_file:
                json.dump(config, config_file)
        finally:
            self._file_lock.release()

    def delete(self, section=None, xdg_config_file=None, xdg_config_dir=None):
        """Delete a top-level section from a configuration file.

        This method is thread safe.

        :param section: A string. The name of the section to be deleted.
        :param xdg_config_file: A string. The name of the file to manipulate.
        :param xdg_config_dir: A string. The XDG configuration directory in
            which the configuration file resides.
        :returns: Nothing.
        """
        # What will we delete?
        if section is None:
            section = self._section

        # What file is being manipulated?
        if xdg_config_file is None:
            xdg_config_file = self._xdg_config_file
        if xdg_config_dir is None:
            xdg_config_dir = self._xdg_config_dir
        path = _get_config_file_path(xdg_config_dir, xdg_config_file)

        # Lock, delete, unlock.
        self._file_lock.acquire()
        try:
            with open(path) as config_file:
                config = json.load(config_file)
            del config[section]
            with open(path, 'w') as config_file:
                json.dump(config, config_file)
        finally:
            self._file_lock.release()

    def sections(self, xdg_config_file=None, xdg_config_dir=None):
        """Read a configuration file and return its top-level sections.

        :param xdg_config_file: A string. The name of the file to manipulate.
        :param xdg_config_dir: A string. The XDG configuration directory in
            which the configuration file resides.
        :returns: An iterable of strings. Each string is the name of a
            configuration file section.
        """
        # What file is being manipulated?
        if xdg_config_file is None:
            xdg_config_file = self._xdg_config_file
        if xdg_config_dir is None:
            xdg_config_dir = self._xdg_config_dir
        path = _get_config_file_path(xdg_config_dir, xdg_config_file)

        with open(path) as config_file:
            # keys() returns a list in Python 2 and a view in Python 3.
            return set(json.load(config_file).keys())

    def read(self, section=None, xdg_config_file=None, xdg_config_dir=None):
        """Read a section from a configuration file.

        :param section: A string. The name of the section to be deleted.
        :param xdg_config_file: A string. The name of the file to manipulate.
        :param xdg_config_dir: A string. The XDG configuration directory in
            which the configuration file resides.
        :returns: A new :class:`pulp_smash.config.ServerConfig` object. The
            current object is not modified by this method.
        :rtype: ServerConfig
        """
        # What section is being read?
        if section is None:
            section = self._section

        # What file is being manipulated?
        if xdg_config_file is None:
            xdg_config_file = self._xdg_config_file
        if xdg_config_dir is None:
            xdg_config_dir = self._xdg_config_dir
        path = _get_config_file_path(xdg_config_dir, xdg_config_file)

        # Instantiate a config and populate it with values from the settings
        # file. We tell the config object which file it has been populated from
        # so calls to its `save` method and other methods hit the same file.
        with open(path) as config_file:
            cfg = type(self)(**json.load(config_file)[section])
        # pylint:disable=protected-access
        cfg._section = section
        cfg._xdg_config_file = xdg_config_file
        cfg._xdg_config_dir = xdg_config_dir
        return cfg

    def get_requests_kwargs(self):
        """Get kwargs for use by the Requests functions.

        This method returns a dict of attributes that can be unpacked and used
        as kwargs via the ``**`` operator. For example:

        >>> cfg = ServerConfig().read()
        >>> requests.get(cfg.base_url + '…', **cfg.get_requests_kwargs())

        This method is useful because client code may not know which attributes
        should be passed from a ``ServerConfig`` object to Requests. Consider
        that the example above could also be written like this:

        >>> cfg = ServerConfig().get()
        >>> requests.get(
        ...     cfg.base_url + '…',
        ...     auth=tuple(cfg.auth),
        ...     verify=cfg.verify
        ... )

        But this latter approach is more fragile. The user must remember to
        convert ``auth`` to a tuple, and it will require maintenance if ``cfg``
        gains or loses attributes.
        """
        attrs = _public_attrs(self)
        for key in ('base_url', 'version'):
            del attrs[key]
        if attrs['auth'] is not None:
            attrs['auth'] = tuple(attrs['auth'])
        return attrs


def _get_config_file_path(xdg_config_dir, xdg_config_file):
    """Search ``XDG_CONFIG_DIRS`` for a config file and return the first found.

    Search each of the standard XDG configuration directories for a
    configuration file. Return as soon as a configuration file is found. Beware
    that by the time client code attempts to open the file, it may be gone or
    otherwise inaccessible.

    :param xdg_config_dir: A string. The name of the directory that is suffixed
        to the end of each of the ``XDG_CONFIG_DIRS`` paths.
    :param xdg_config_file: A string. The name of the configuration file that
        is being searched for.
    :returns: A string. A path to a configuration file.
    :raises pulp_smash.config.ConfigFileNotFoundError: If the requested
        configuration file cannot be found.
    """
    for config_dir in BaseDirectory.load_config_paths(xdg_config_dir):
        path = os.path.join(config_dir, xdg_config_file)
        if os.path.isfile(path):
            return path
    raise ConfigFileNotFoundError(
        'No configuration files could be located after searching for a file '
        'named "{0}" in the standard XDG configuration paths, such as '
        '"~/.config/{1}/".'.format(xdg_config_file, xdg_config_dir)
    )
