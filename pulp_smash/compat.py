# coding=utf-8
"""Provides modules that would otherwise require a try/except block.

This module provides modules that are available at different namespaces in
different versions of Python.
"""
from __future__ import unicode_literals
# pylint:disable=unused-import

try:  # try Python 3 import first
    from io import StringIO
    from urllib.parse import quote_plus, urljoin, urlparse, urlunparse
except ImportError:
    from StringIO import StringIO  # noqa
    from urllib import quote_plus  # noqa pylint:disable=ungrouped-imports
    from urlparse import urljoin, urlparse, urlunparse  # noqa
