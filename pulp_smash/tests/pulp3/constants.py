# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin


BASE_PATH = '/api/v3/'

BASE_IMPORTER_PATH = urljoin(BASE_PATH, 'importers/')

BASE_PUBLISHER_PATH = urljoin(BASE_PATH, 'publishers/')

FILE_IMPORTER_PATH = urljoin(BASE_IMPORTER_PATH, 'file/')

FILE_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'file/')

IMPORTER_DOWN_POLICY = {'background', 'immediate', 'on_demand'}
"""Download policies for an importer.

See `pulpcore.app.models.Importer
<https://docs.pulpproject.org/en/3.0/nightly/contributing/platform_api/app/models.html#pulpcore.app.models.Importer>`_.
"""

IMPORTER_SYNC_MODE = {'additive', 'mirror'}
"""Sync modes for an importer.

See `pulpcore.app.models.Importer
<https://docs.pulpproject.org/en/3.0/nightly/contributing/platform_api/app/models.html#pulpcore.app.models.Importer>`_.
"""

JWT_PATH = urljoin(BASE_PATH, 'jwt/')

REPO_PATH = urljoin(BASE_PATH, 'repositories/')

STATUS_PATH = urljoin(BASE_PATH, 'status/')

USER_PATH = urljoin(BASE_PATH, 'users/')
