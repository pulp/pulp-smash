# coding=utf-8
"""Constants for Pulp 3 tests."""
from urllib.parse import urljoin

from pulp_smash.api import (  # noqa: F401
    _P3_TASK_END_STATES as P3_TASK_END_STATES,
)

BASE_PATH = "/pulp/api/v3/"

API_DOCS_PATH = urljoin(BASE_PATH, "docs/")

ARTIFACTS_PATH = urljoin(BASE_PATH, "artifacts/")

BASE_CONTENT_GUARDS_PATH = urljoin(BASE_PATH, "contentguards/")

BASE_PUBLISHER_PATH = urljoin(BASE_PATH, "publishers/")

BASE_REMOTE_PATH = urljoin(BASE_PATH, "remotes/")

CONTENT_PATH = urljoin(BASE_PATH, "content/")

DISTRIBUTION_PATH = urljoin(BASE_PATH, "distributions/")

IMMEDIATE_DOWNLOAD_POLICIES = ("immediate",)

ON_DEMAND_DOWNLOAD_POLICIES = ("on_demand", "streamed")

MEDIA_PATH = "/var/lib/pulp"

ORPHANS_PATH = urljoin(BASE_PATH, "orphans/")

PUBLICATIONS_PATH = urljoin(BASE_PATH, "publications/")

REPO_PATH = urljoin(BASE_PATH, "repositories/")

STATUS_PATH = urljoin(BASE_PATH, "status/")

TASKS_PATH = urljoin(BASE_PATH, "tasks/")

WORKER_PATH = urljoin(BASE_PATH, "workers/")
