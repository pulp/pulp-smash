# coding=utf-8
"""Tools for manipulating XDG-compliant JSON configuration files.

This module builds upon the XDG Base Directory Specification and the PyXDG
library. What are they?

* The `XDG Base Directory Specification`_ provides guidance to Linux
  applications. It defines where applications should place and look for data,
  configuration, cache and runtime files.
* "`PyXDG`_ is a Python library supporting various freedesktop standards,"
  including the `XDG Base Directory Specification`_.

The existing specification and library are useful, but generic. Applications
still have to answer questions like "should my configuration file be INI, JSON,
YAML, SQLite or something else?" and "how do I modify my configuration file in
a thread-safe way?" This module answers those questions. The curious should
start by reading up on :class:`ConfigSection`.

.. _PyXDG: http://freedesktop.org/wiki/Software/pyxdg/
.. _XDG Base Directory Specification:
    http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

"""
from __future__ import unicode_literals

import json
from os.path import isfile, join
from threading import Lock
from xdg import BaseDirectory


class ConfigFileNotFoundError(Exception):
    """Indicates that the requested XDG configuration file cannot be found."""


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
    :raises pulp_smash.config.base.ConfigFileNotFoundError: If the requested
        configuration file cannot be found.

    """
    for config_dir in BaseDirectory.load_config_paths(xdg_config_dir):
        path = join(config_dir, xdg_config_file)
        if isfile(path):
            return path
    raise ConfigFileNotFoundError(
        'No configuration files could be located after searching for a file '
        'named "{0}" in the standard XDG configuration paths, such as '
        '"~/.config/{1}/".'.format(xdg_config_file, xdg_config_dir)
    )


class ConfigSection(dict):
    """A dict-like object with methods for manipulating configuration files.

    A :class:`ConfigSection` object represents a top-level section of a
    configuration file. (It does *not* represent an entire configuration file,
    or a sub-section of a configuration file.) One can :meth:`save` it out to a
    file, :meth:`read` it back and more.

    By way of example, assume that a file with the following contents exists on
    the filesystem::

        {
          "default": {"hostname": "example.com", "auth": ["alice", "hackme"]},
          "alternate": {"hostname": "example.org", "auth": ["bob", "hackme"]},
        }

    The two top-level sections can be read like so:

    >>> from pulp_smash.config.base import ConfigSection
    >>> default = ConfigSection.read('default')
    >>> alternate = ConfigSection.read('alternate')
    >>> default == {'hostname': 'example.com', 'auth': ['alice', 'hackme']}
    True
    >>> alternate == {'hostname': 'example.org', 'auth': ['bob', 'hackme']}
    True

    By default, :meth:`read` works with the "default" section. As a result,
    this holds true:

    >>> from pulp_smash.config.base import ConfigSection
    >>> ConfigSection.read() == ConfigSection.read('default')
    >>> ConfigSection.read() != ConfigSection.read('alternate')

    It's possible to do more than just read configuration file sections. Please
    explore the other methods on this class to learn their details. The
    ``_xdg_config_dir`` and ``_xdg_config_file`` class attributes influence
    these methods. All subclasses must set at least ``_xdg_config_dir``.

    """
    # Used to lock access to the configuration file when performing destructive
    # operations, such as saving.
    _file_lock = Lock()
    # The name of the directory appended to ``XDG_CONFIG_DIRS``.
    _xdg_config_dir = None
    # The name of the file in which settings are stored.
    _xdg_config_file = 'settings.json'

    def __repr__(self):
        return '{}({})'.format(
            type(self).__name__,
            ', '.join(
                '{0}={1}'.format(key, repr(value))
                for key, value
                in self.items()
            )
        )

    def save(self, section='default', path=None, data=None):
        """Save ``self`` as a top-level section of a configuration file.

        This method is thread safe, but not process safe.

        Beware that this method serializes the contents of the current object
        to JSON. If any data cannot be serialized to JSON, an exception is
        raised. This can be solved by using one of the
        :mod:`pulp_smash.config.mixins` or writing your own.

        :param section: A string. An identifier for the current configuration.
            If no section named ``section`` exists in the configuration file,
            one is created. If a section named ``section`` already exists, it
            is replaced.
        :param path: A string. The configuration file to be manipulated. If the
            destination file does not exist, it is created. If no path is
            provided, an XDG-compliant path is generated.
        :returns: Nothing.

        """
        # What will we write out? What file is receiving this data?
        if data is None:
            data = self.copy()
        if path is None:
            path = join(
                BaseDirectory.save_config_path(self._xdg_config_dir),
                self._xdg_config_file
            )

        # Lock, write out `data` and unlock.
        self._file_lock.acquire()
        try:
            try:
                with open(path) as config_file:
                    config = json.load(config_file)
            except IOError:
                config = {}
            config[section] = data
            with open(path, 'w') as config_file:
                json.dump(config, config_file)
        finally:
            self._file_lock.release()

    @classmethod
    def delete(cls, section='default', path=None):
        """Delete a top-level section from a configuration file.

        This method is thread safe.

        :param section: A string. The section to be deleted.
        :param path: A string. The configuration file to be manipulated.
            Defaults to what is returned by
            :func:`pulp_smash.config.base._get_config_file_path`.
        :returns: Nothing.

        """
        if path is None:
            path = _get_config_file_path(
                cls._xdg_config_dir,
                cls._xdg_config_file
            )
        cls._file_lock.acquire()
        try:
            with open(path) as config_file:
                config = json.load(config_file)
            del config[section]
            with open(path, 'w') as config_file:
                json.dump(config, config_file)
        finally:
            cls._file_lock.release()

    @classmethod
    def sections(cls, path=None):
        """Read a configuration file and return its top-level sections.

        :param path: A string. The configuration file to be manipulated.
            Defaults to what is returned by
            :func:`pulp_smash.config.base._get_config_file_path`.
        :returns: An iterable containing strings. Each string is the name of a
            configuration file section.

        """
        if path is None:
            path = _get_config_file_path(
                cls._xdg_config_dir,
                cls._xdg_config_file
            )
        with open(path) as config_file:
            # keys() returns a list in Python 2 and a view in Python 3.
            return tuple(json.load(config_file).keys())

    @classmethod
    def read(cls, section='default', path=None):
        """Read a section from a configuration file.

        :param section: A string. The name of the section to read.
        :param path: A string. The configuration file to be manipulated.
            Defaults to what is returned by
            :func:`pulp_smash.config.base._get_config_file_path`.
        :returns: A new :class:`pulp_smash.config.base.ConfigSection` object.
            The current object is not modified when this method is called.
        :rtype: ConfigSection

        """
        if path is None:
            path = _get_config_file_path(
                cls._xdg_config_dir,
                cls._xdg_config_file
            )
        with open(path) as config_file:
            return cls(**json.load(config_file)[section])
