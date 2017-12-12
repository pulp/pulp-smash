# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/api/v3/'

BASE_IMPORTER_PATH = urljoin(BASE_PATH, 'importers/')

FILE_IMPORTER_PATH = urljoin(BASE_IMPORTER_PATH, 'file/')

IMPORTER_DOWN_POLICY = {'background', 'immediate', 'on_demand'}

IMPORTER_SYNC_MODE = {'additive', 'mirror'}

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

STATUS_PATH = urljoin(BASE_PATH, 'status/')

USER_PATH = urljoin(BASE_PATH, 'users/')
