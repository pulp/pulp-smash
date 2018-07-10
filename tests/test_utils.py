# coding=utf-8
"""Unit tests for :mod:`pulp_smash.utils`."""
import unittest
from unittest import mock

from pulp_smash import cli, utils


class UUID4TestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.uuid4`."""

    def test_type(self):
        """Assert the method returns a unicode string."""
        self.assertIsInstance(utils.uuid4(), str)


class IsRootTestCase(unittest.TestCase):
    """Test ``pulp_smash.cli.is_root``."""

    def test_true(self):
        """Assert the method returns ``True`` when root."""
        with mock.patch.object(cli, 'Client') as clien:
            clien.return_value.run.return_value.stdout.strip.return_value = '0'
            self.assertTrue(cli.is_root(None))

    def test_false(self):
        """Assert the method returns ``False`` when non-root."""
        with mock.patch.object(cli, 'Client') as clien:
            clien.return_value.run.return_value.stdout.strip.return_value = '1'
            self.assertFalse(cli.is_root(None))


class GetSha256ChecksumTestCase(unittest.TestCase):
    """Test :func:`pulp_smash.utils.get_sha256_checksum`."""

    def test_all(self):
        """Call the function three times, with two URLs.

        Call the function with the first URL, the second URL and the first URL
        again. Verify that:

        * No download is attempted during the third call.
        * The first and second calls return different checksums.
        * The first and third calls return identical checksums.
        """
        urls_blobs = (
            ('http://example.com', b'abc'),
            ('http://example.org', b'123'),
            ('HTTP://example.com', b'abc'),
        )
        checksums = []
        with mock.patch.object(utils, 'http_get') as http_get:
            for url, blob in urls_blobs:
                http_get.return_value = blob
                checksums.append(utils.get_sha256_checksum(url))
        self.assertEqual(http_get.call_count, 2)
        self.assertNotEqual(checksums[0], checksums[1])
        self.assertEqual(checksums[0], checksums[2])


class GetOsReleaseTestCase(unittest.TestCase):
    """Test the ``get_os_release_*`` functions.

    These tests are very simple: they just make sure that the string returned
    by the used :class:`pulp_smash.cli.Client` object is stripped and returned.
    """

    def test_get_os_release_id(self):
        """Test :func:`pulp_smash.utils.get_os_release_id`."""
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.stdout = ' fedora '
            response = utils.get_os_release_id(mock.Mock())
        self.assertEqual(response, 'fedora')

    def test_get_os_release_version_id(self):
        """Test :func:`pulp_smash.utils.get_os_release_version_id`."""
        with mock.patch.object(cli, 'Client') as client:
            client.return_value.run.return_value.stdout = ' 27 '
            response = utils.get_os_release_version_id(mock.Mock())
        self.assertEqual(response, '27')
