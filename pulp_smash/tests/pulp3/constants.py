# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/api/v3/'

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

USER_PATH = urljoin(BASE_PATH, 'users/')
