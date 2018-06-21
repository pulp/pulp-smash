"""Unit tests for pulp_smash.pulp3.utils."""

import unittest

from pulp_smash.pulp3.utils import gen_distribution, gen_remote, gen_repo


class GenTestCase(unittest.TestCase):
    """Tests the `gen_` functions."""

    def test_gen_distribution(self):
        """Asserts the generation of distibution dict."""
        self.assertIn('base_path', gen_distribution())
        self.assertIn('name', gen_distribution())

        dist = gen_distribution(name='foodist')
        self.assertIn('base_path', dist)
        self.assertEqual('foodist', dist['name'])

    def test_gen_remote(self):
        """Asserts the generation of remote dict."""
        self.assertIn('url', gen_remote('http://foo.com'))
        self.assertIn('name', gen_remote('http://foo.com'))
        self.assertEqual('http://foo.com', gen_remote('http://foo.com')['url'])

        rem = gen_remote('http://fooremote', name='fooremote')
        self.assertIn('url', rem)
        self.assertEqual('http://fooremote', rem['url'])
        self.assertEqual('fooremote', rem['name'])

    def test_gen_repo(self):
        """Asserts the generation of repository dict."""
        self.assertIn('notes', gen_repo())
        self.assertIn('name', gen_repo())

        repo = gen_repo(name='foorepo')
        self.assertIn('notes', repo)
        self.assertEqual('foorepo', repo['name'])
