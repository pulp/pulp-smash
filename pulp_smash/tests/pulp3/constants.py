# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/pulp/api/v3/'

API_DOCS_PATH = urljoin(BASE_PATH, 'docs/')

ARTIFACTS_PATH = urljoin(BASE_PATH, 'artifacts/')

BASE_REMOTE_PATH = urljoin(BASE_PATH, 'remotes/')

BASE_PUBLISHER_PATH = urljoin(BASE_PATH, 'publishers/')

CONTENT_PATH = urljoin(BASE_PATH, 'content/')

DISTRIBUTION_PATH = urljoin(BASE_PATH, 'distributions/')

FILE_CONTENT_PATH = urljoin(CONTENT_PATH, 'file/')

FILE_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'file/')

FILE_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'file/')

PYTHON_CONTENT_PATH = urljoin(CONTENT_PATH, 'python/')

PYTHON_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'python/')

PYTHON_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'python/')

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

ORPHANS_PATH = urljoin(BASE_PATH, 'orphans/')

PUBLICATIONS_PATH = urljoin(BASE_PATH, 'publications/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

STATUS_PATH = urljoin(BASE_PATH, 'status/')

USER_PATH = urljoin(BASE_PATH, 'users/')

WORKER_PATH = urljoin(BASE_PATH, 'workers/')
