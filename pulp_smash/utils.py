# coding=utf-8
"""Utility functions for Pulp tests."""
from __future__ import unicode_literals

from uuid import uuid4


def rand_str():
    """Return a randomized string."""
    return type('')(uuid4())
