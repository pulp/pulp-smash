# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/api/v3/'

ARTIFACTS_PATH = urljoin(BASE_PATH, 'artifacts/')

BASE_IMPORTER_PATH = urljoin(BASE_PATH, 'importers/')

BASE_PUBLISHER_PATH = urljoin(BASE_PATH, 'publishers/')

CONTENT_PATH = urljoin(BASE_PATH, 'content/')

DISTRIBUTION_PATH = urljoin(BASE_PATH, 'distributions/')

FILE_CONTENT_PATH = urljoin(CONTENT_PATH, 'file/')

FILE_IMPORTER_PATH = urljoin(BASE_IMPORTER_PATH, 'file/')

FILE_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'file/')

IMPORTER_DOWN_POLICY = {'background', 'immediate', 'on_demand'}
"""Download policies for an importer.

See `pulpcore.app.models.Importer
<https://docs.pulpproject.org/en/3.0/nightly/contributing/platform_api/app/models.html#pulpcore.app.models.Importer>`_.
"""

IMPORTER_SYNC_MODE = {'mirror'}
"""Sync modes for an importer.

See `pulpcore.app.models.Importer
<https://docs.pulpproject.org/en/3.0/nightly/contributing/platform_api/app/models.html#pulpcore.app.models.Importer>`_.
"""

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

PUBLICATIONS_PATH = urljoin(BASE_PATH, 'publications/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

STATUS_PATH = urljoin(BASE_PATH, 'status/')

USER_PATH = urljoin(BASE_PATH, 'users/')
