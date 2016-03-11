# coding=utf-8
"""Compatibility imports."""

try:  # try Python 3 import first
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin  # pylint:disable=C0411,E0401,F0401 # noqa
