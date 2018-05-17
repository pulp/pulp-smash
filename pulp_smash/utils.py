# coding=utf-8
"""Utility functions for Pulp tests.

This module may make use of :mod:`pulp_smash.api` and :mod:`pulp_smash.cli`,
but the reverse should not be done.
"""
import hashlib
import uuid
from urllib.parse import urlparse

import requests

from pulp_smash import cli
from pulp_smash.cli import _is_root as is_root  # pylint:disable=unused-import

# A mapping between URLs and SHA 256 checksums. Used by get_sha256_checksum().
_CHECKSUM_CACHE = {}


class SmokeTest():  # pylint:disable=too-few-public-methods
    """A class for identifying smoke tests.

    Classes that inherit from this class are considered smoke tests, and may be
    returned by Pulp Smash's CLI. (See :mod:`pulp_smash.pulp_smash_cli`.)
    """
    # Which test cases should be marked as smoke tests? For Pulp 3, a sane
    # solution is to include test cases that belong to the Pulp 3 smoke tests
    # milestone. [1] For Pulp 2, no similar milestone exists.
    #
    # [1] https://github.com/PulpQE/pulp-smash/milestone/22


def get_sha256_checksum(url):
    """Return the sha256 checksum of the file at the given URL.

    When a URL is encountered for the first time, do the following:

    1. Download the file and calculate its sha256 checksum.
    2. Cache the URL-checksum pair.
    3. Return the checksum.

    On subsequent calls, return a cached checksum.
    """
    # URLs are normalized before checking the cache and possibly downloading
    # files. Otherwise, unnecessary downloads and cache entries may be made.
    url = urlparse(url).geturl()
    if url not in _CHECKSUM_CACHE:
        checksum = hashlib.sha256(http_get(url)).hexdigest()
        _CHECKSUM_CACHE[url] = checksum
    return _CHECKSUM_CACHE[url]


def http_get(url, **kwargs):
    """Issue a HTTP request to the ``url`` and return the response content.

    This is useful for downloading file contents over HTTP[S].

    :param url: the URL where the content should be get.
    :param kwargs: additional kwargs to be passed to ``requests.get``.
    :returns: the response content of a GET request to ``url``.
    """
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response.content


def os_is_f26(cfg, pulp_host=None):
    """Return ``True`` if the server runs Fedora 26, or ``False`` otherwise.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted.
    :param pulp_host: A :class:`pulp_smash.config.PulpHost` to target,
        instead of the default chosen by :class:`pulp_smash.cli.Client`.
    :returns: True or false.
    """
    response = cli.Client(cfg, cli.echo_handler, pulp_host).run((
        'grep',
        '-i',
        'fedora release 26',
        '/etc/redhat-release',
    ))
    return response.returncode == 0


def os_is_f27(cfg, pulp_host=None):
    """Return ``True`` if the server runs Fedora 27, or ``False`` otherwise.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted.
    :param pulp_host: A :class:`pulp_smash.config.PulpHost` to target,
        instead of the default chosen by :class:`pulp_smash.cli.Client`.
    :returns: True or false.
    """
    response = cli.Client(cfg, cli.echo_handler, pulp_host).run((
        'grep',
        '-i',
        'fedora release 27',
        '/etc/redhat-release',
    ))
    return response.returncode == 0


def uuid4():
    """Return a random UUID4 as a string."""
    return str(uuid.uuid4())
