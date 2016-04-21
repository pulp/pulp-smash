# coding=utf-8
"""Provides modules that would otherwise require a try/except block.

This module provides modules that are available at different namespaces in
different versions of Python.
"""
from __future__ import unicode_literals

try:  # try Python 3 import first
    from urllib.parse import quote_plus, urljoin, urlparse, urlunparse
except ImportError:
    from urllib import quote_plus  # noqa
    from urlparse import urljoin, urlparse, urlunparse  # noqa pylint:disable=C0411,E0401,F0401
