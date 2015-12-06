# coding=utf-8
"""Unit tests for :mod:`pulp_smash.utils`."""
from __future__ import unicode_literals

import mock
import requests
from pulp_smash import utils
from pulp_smash.config import ServerConfig
from unittest2 import TestCase


class UUID4TestCase(TestCase):
    """Test :meth:`pulp_smash.utils.uuid4`."""

    def test_type(self):
        """Assert the method returns a unicode string."""
        self.assertIsInstance(utils.uuid4(), type(''))


class CommonAssertionsMixin(object):
    """A common set of assertions for generic helper functions.

    Some helper functions have a signature of ``func(server_config, …,
    responses)``. This class provides test methods that can be used with any of
    those functions. These methods only work if the following attributes can be
    accessed:

    =================================  ========================================
    attribute                          purpose
    =================================  ========================================
    ``self.mocks['request']``          A mock object stubbing one of the
                                       functions in the ``requests`` module.
    ``self.mocks['handle_response']``  A mock object stubbing the
                                       ``pulp_smash.utils.handle_response``
                                       function.
    ``self.output``                    The value returned by the function under
                                       test.
    =================================  ========================================

    """

    def test_requests_called(self):
        """Assert the Requests function is called once."""
        self.assertEqual(self.mocks['request'].call_count, 1)

    def test_handle_response_called(self):
        """Assert ``handle_response`` is called once."""
        self.assertEqual(self.mocks['handle_response'].call_count, 1)

    def test_return_value(self):
        """Assert that whatever ``handle_response`` returns is returned."""
        self.assertIs(self.mocks['handle_response'].return_value, self.output)


class CreateRepositoryTestCase(CommonAssertionsMixin, TestCase):
    """Test :meth:`pulp_smash.utils.create_repository`."""

    @classmethod
    def setUpClass(cls):
        """Mock out dependencies and call the function under test."""
        inputs = {
            'server_config': ServerConfig('http://example.com'),
            'body': None,
            'responses': None,
        }
        with mock.patch.object(utils, 'handle_response') as hand_resp:
            with mock.patch.object(requests, 'post') as request:
                cls.output = utils.create_repository(**inputs)
        cls.mocks = {'handle_response': hand_resp, 'request': request}


class CreateUserTestCase(CommonAssertionsMixin, TestCase):
    """Test :meth:`pulp_smash.utils.create_user`."""

    @classmethod
    def setUpClass(cls):
        """Mock out dependencies and call the function under test."""
        inputs = {
            'server_config': ServerConfig('http://example.com'),
            'body': None,
            'responses': None,
        }
        with mock.patch.object(utils, 'handle_response') as hand_resp:
            with mock.patch.object(requests, 'post') as request:
                cls.output = utils.create_user(**inputs)
        cls.mocks = {'handle_response': hand_resp, 'request': request}


class DeleteTestCase(CommonAssertionsMixin, TestCase):
    """Test :meth:`pulp_smash.utils.delete`."""

    @classmethod
    def setUpClass(cls):
        """Mock out dependencies and call the function under test."""
        inputs = {
            'server_config': ServerConfig('http://example.com'),
            'href': utils.uuid4(),
            'responses': None,
        }
        with mock.patch.object(utils, 'handle_response') as hand_resp:
            with mock.patch.object(requests, 'delete') as request:
                cls.output = utils.delete(**inputs)
        cls.mocks = {'handle_response': hand_resp, 'request': request}


class GetImportersTestCase(CommonAssertionsMixin, TestCase):
    """Test :meth:`pulp_smash.utils.get_importers`."""

    @classmethod
    def setUpClass(cls):
        """Mock out dependencies and call the function under test."""
        inputs = {
            'server_config': ServerConfig('http://example.com'),
            'href': utils.uuid4(),
            'responses': None,
        }
        with mock.patch.object(utils, 'handle_response') as hand_resp:
            with mock.patch.object(requests, 'get') as request:
                cls.output = utils.get_importers(**inputs)
        cls.mocks = {'handle_response': hand_resp, 'request': request}


class PublishRepositoryTestCase(CommonAssertionsMixin, TestCase):
    """Test :meth:`pulp_smash.utils.publish_repository`."""

    @classmethod
    def setUpClass(cls):
        """Mock out dependencies and call the function under test."""
        inputs = {
            'server_config': ServerConfig('http://example.com'),
            'href': utils.uuid4(),
            'distributor_id': None,
            'responses': None,
        }
        with mock.patch.object(utils, 'handle_response') as hand_resp:
            with mock.patch.object(requests, 'post') as request:
                cls.output = utils.publish_repository(**inputs)
        cls.mocks = {'handle_response': hand_resp, 'request': request}


class SyncRepositoryTestCase(CommonAssertionsMixin, TestCase):
    """Test :meth:`pulp_smash.utils.sync_repository`."""

    @classmethod
    def setUpClass(cls):
        """Mock out dependencies and call the function under test."""
        inputs = {
            'server_config': ServerConfig('http://example.com'),
            'href': utils.uuid4(),
            'responses': None,
        }
        with mock.patch.object(utils, 'handle_response') as hand_resp:
            with mock.patch.object(requests, 'post') as request:
                cls.output = utils.sync_repository(**inputs)
        cls.mocks = {'handle_response': hand_resp, 'request': request}
