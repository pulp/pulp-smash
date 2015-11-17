# coding=utf-8
"""Utility functions for Pulp tests."""
from __future__ import unicode_literals

import uuid


def uuid4():
    """Return a random UUID, as a unicode string."""
    return type('')(uuid.uuid4())
