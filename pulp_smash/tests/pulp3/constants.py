# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/api/v3/'

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

USER_PATH = urljoin(BASE_PATH, 'users/')
