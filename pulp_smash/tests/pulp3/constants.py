# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/api/v3/'

API_DOCS_PATH = urljoin(BASE_PATH, 'docs/')

ARTIFACTS_PATH = urljoin(BASE_PATH, 'artifacts/')

BASE_REMOTE_PATH = urljoin(BASE_PATH, 'remotes/')

BASE_PUBLISHER_PATH = urljoin(BASE_PATH, 'publishers/')

CONTENT_PATH = urljoin(BASE_PATH, 'content/')

DISTRIBUTION_PATH = urljoin(BASE_PATH, 'distributions/')

FILE_CONTENT_PATH = urljoin(CONTENT_PATH, 'file/')

FILE_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'file/')

FILE_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'file/')

REMOTE_DOWN_POLICY = {'background', 'immediate', 'on_demand'}
"""Download policies for an remote.

See `pulpcore.app.models.Remote
<https://docs.pulpproject.org/en/3.0/nightly/contributing/platform_api/app/models.html#pulpcore.app.models.Remote>`_.
"""

REMOTE_SYNC_MODE = {'mirror'}
"""Sync modes for an remote.

See `pulpcore.app.models.Remote
<https://docs.pulpproject.org/en/3.0/nightly/contributing/platform_api/app/models.html#pulpcore.app.models.Remote>`_.
"""

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

ORPHANS_PATH = urljoin(BASE_PATH, 'orphans/')

PUBLICATIONS_PATH = urljoin(BASE_PATH, 'publications/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

STATUS_PATH = urljoin(BASE_PATH, 'status/')

USER_PATH = urljoin(BASE_PATH, 'users/')
