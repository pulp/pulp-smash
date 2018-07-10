# coding=utf-8
"""Utility functions for Pulp tests.

This module may make use of :mod:`pulp_smash.api` and :mod:`pulp_smash.cli`,
but the reverse should not be done.
"""
import hashlib
import uuid
from urllib.parse import urlparse

import requests

from pulp_smash import cli, exceptions

# A mapping between URLs and SHA 256 checksums. Used by get_sha256_checksum().
_CHECKSUM_CACHE = {}


def get_os_release_id(cfg, pulp_host=None):
    """Get ``ID`` from ``/etc/os-release``.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted.
    :param pulp_host: A :class:`pulp_smash.config.PulpHost` to target,
        instead of the default chosen by :class:`pulp_smash.cli.Client`.
    :returns: A string such as "rhel," "fedora," or "arch." (These values come
        from Red Hat Enterprise Linux, Fedora, and Arch Linux respectively.)
    """
    return cli.Client(cfg, pulp_host=pulp_host).run((
        'bash',
        '-c',
        '(source /etc/os-release && echo "$ID")',
    )).stdout.strip()


def get_os_release_version_id(cfg, pulp_host=None):
    """Get ``VERSION_ID`` from ``/etc/os-release``.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted.
    :param pulp_host: A :class:`pulp_smash.config.PulpHost` to target,
        instead of the default chosen by :class:`pulp_smash.cli.Client`.
    :returns: A string such as "7.5" or "27". (These values come from RHEL 7.5
        and Fedora 27, respectively.) Make sure to convert this string to an
        actual version object if doing version number comparisons.
        ``packaging.version.Version`` can be used for this purpose.
    """
    return cli.Client(cfg, pulp_host=pulp_host).run((
        'bash',
        '-c',
        '(source /etc/os-release && echo "$VERSION_ID")',
    )).stdout.strip()


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


def fips_is_supported(cfg, pulp_host=None):
    """Return ``True`` if the server supports Fips, or ``False`` otherwise.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted
    :param pulp_host: A :class : `pulp_smash.config.PulpHost` to target,
        instead of the default chosen by :class: pulp_smash.cli.Client`.
    :return: True of False
    """
    try:
        cli.Client(cfg, pulp_host=pulp_host).run((
            'sysctl',
            'crypto.fips_enabled'
        ))
    except exceptions.CalledProcessError:
        return False
    return True


def fips_is_enabled(cfg, pulp_host=None):
    """Return ``True`` if the Fips is enabled in server, or ``False`` otherwise.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted
    :param pulp_host: A :class : `pulp_smash.config.PulpHost` to target,
        instead of the default chosen by :class: pulp_smash.cli.Client`.
    :return: True of False
    """
    return cli.Client(cfg, pulp_host=pulp_host).run((
        'sysctl',
        '--values',
        'crypto.fips_enabled'
    )).stdout.strip() == '1'


def uuid4():
    """Return a random UUID4 as a string."""
    return str(uuid.uuid4())
