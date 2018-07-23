"""Values usable by multiple test modules."""


PULP_FIXTURES_BASE_URL = 'https://repos.fedorapeople.org/pulp/pulp/fixtures/'
"""A URL at which generated `pulp fixtures`_ are hosted.

.. _pulp fixtures: https://github.com/PulpQE/pulp-fixtures/
"""

PULP_FIXTURES_KEY_ID = '269d9d98'
"""The 32-bit ID of the public key used to sign various fixture files.

To calculate a new key ID, find the public key used by Pulp Fixtures (it should
be in the Pulp Fixtures source code repository) and use GnuPG to examine it::

    $ gpg "$public_key_file"
    pub   rsa2048 2016-08-05 [SC]
          6EDF301256480B9B801EBA3D05A5E6DA269D9D98
    uid           Pulp QE
    sub   rsa2048 2016-08-05 [E]

The last 32 bits (8 characters) of the key ID are what Pulp wants — in this
example, 269D9D98.
"""
