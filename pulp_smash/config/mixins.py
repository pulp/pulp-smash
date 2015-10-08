# coding=utf-8
"""Mixins for :class:`pulp_smash.config.base.ConfigSection`.

.. WARNING: All child classes **must list all mixins before
    :class:`pulp_smash.config.base.ConfigSection`**! To illustrate::

        class Child(VersionMixin, ConfigSection):  # OK: mixins listed first
        class Child(ConfigSection, VersionMixin):  # Bad: mixin listed after

    This constraint arises because mixins may extend methods defined on
    ``ConfigSection``, and it is important that the extending methods be called
    first. For more information, read up on Method Resolution Order (MRO).

"""
from __future__ import unicode_literals


class AuthMixin(object):
    """A mixin that treats the "auth" attribute specially.

    The Requests library is capable of performing several types of
    authentication via its ``auth`` argument. If ``auth`` is a two-tuple, HTTP
    Basic authentication is performed. For example:

    >>> response = requests.get('http://example.com', auth=('foo', 'bar'))

    This is problematic because :class:`pulp_smash.config.base.ConfigSection`
    uses the JSON decoder when fetching values from configuration files, and
    the JSON decoder creates and returns a list whenever an array is found.
    This mixin causes :meth:`read` to cast the ``auth`` attribute to a
    two-tuple if ``auth`` is present and is a list.

    """
    # pylint:disable=too-few-public-methods
    # This class is intentionally small. It's a mixin, not a stand alone class.

    @classmethod
    def read(cls, section='default', path=None):
        """Cast "auth" to a two-tuple if present and if a list."""
        config = super(AuthMixin, cls).read(section, path)
        if 'auth' in config and isinstance(config['auth'], list):
            config['auth'] = tuple(config['auth'])
        return config
