# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin

from pulp_smash.api import _P3_TASK_END_STATES as P3_TASK_END_STATES  # pylint:disable=unused-import

BASE_PATH = '/pulp/api/v3/'

API_DOCS_PATH = urljoin(BASE_PATH, 'docs/')

ARTIFACTS_PATH = urljoin(BASE_PATH, 'artifacts/')

BASE_REMOTE_PATH = urljoin(BASE_PATH, 'remotes/')

BASE_PUBLISHER_PATH = urljoin(BASE_PATH, 'publishers/')

CONTENT_GUARDS_PATH = urljoin(BASE_PATH, 'content-guards/')

CONTENT_PATH = urljoin(BASE_PATH, 'content/')

DISTRIBUTION_PATH = urljoin(BASE_PATH, 'distributions/')

DOWNLOAD_POLICIES = ['immediate', 'on_demand', 'streamed']

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

MEDIA_PATH = '/var/lib/pulp'

ORPHANS_PATH = urljoin(BASE_PATH, 'orphans/')

PUBLICATIONS_PATH = urljoin(BASE_PATH, 'publications/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

STATUS_PATH = urljoin(BASE_PATH, 'status/')

TASKS_PATH = urljoin(BASE_PATH, 'tasks/')

USER_PATH = urljoin(BASE_PATH, 'users/')

WORKER_PATH = urljoin(BASE_PATH, 'workers/')
