# coding=utf-8
"""Utility functions for Pulp 3 tests."""
from collections import defaultdict
import warnings
from urllib.parse import urljoin, urlsplit

from packaging.version import Version

from pulp_smash import api, config, utils
from pulp_smash.pulp3.constants import ORPHANS_PATH, STATUS_PATH


def require_pulp_3(exc):
    """Raise an exception if Pulp 3 isn't under test.

    If the same exception should be pased each time this method is called,
    consider using `functools.partial`_.

    :param exc: A class to instantiate and raise as an exception. Its
        constructor must accept one string argument.

    .. _functools.partial:
        https://docs.python.org/3/library/functools.html#functools.partial
    """
    cfg = config.get_config()
    if not Version('3') <= cfg.pulp_version < Version('4'):
        raise exc(
            'These tests are for Pulp 3, but Pulp {} is under test.'
            .format(cfg.pulp_version)
        )


def require_pulp_plugins(required_plugins, exc):
    """Raise an exception if one or more plugins are missing.

    If the same exception should be pased each time this method is called,
    consider using `functools.partial`_.

    :param required_plugins: A set of plugin names, e.g. ``{'pulp-file'}``.
    :param exc: A class to instantiate and raise as an exception. Its
        constructor must accept one string argument.

    .. _functools.partial:
        https://docs.python.org/3/library/functools.html#functools.partial
    """
    missing_plugins = required_plugins - get_plugins()
    if missing_plugins:
        raise exc(
            'The following plugins are required but not installed: {}'
            .format(missing_plugins)
        )


def get_plugins(cfg=None):
    """Return the set of plugins installed on the Pulp application.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        application under test.
    :returns: A set of plugin names, e.g. ``{'pulpcore', 'pulp_file'}``.
    """
    if not cfg:
        cfg = config.get_config()
    client = api.Client(cfg, api.json_handler)
    status = client.get(STATUS_PATH)
    return {version['component'] for version in status['versions']}


def sync(cfg, remote, repo, **kwargs):
    """Sync a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param remote: A dict of information about the remote of the repository
        to be synced.
    :param repo: A dict of information about the repository.
    :param kwargs: Keyword arguments to be merged in to the request data.
    :returns: The server's response. Call ``.json()`` on the response to get
        a call report.
    """
    client = api.Client(cfg, api.json_handler)
    data = {'repository': repo['_href']}
    data.update(kwargs)
    return client.post(urljoin(remote['_href'], 'sync/'), data)


def publish(cfg, publisher, repo, version_href=None):
    """Publish a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param publisher: A dict of information about the publisher of the
        repository to be published.
    :param repo: A dict of information about the repository.
    :param version_href: The repository version to be published.
    :returns: A publication. A dict of information about the just created
        publication.
    """
    if version_href is None:
        body = {'repository': repo['_href']}
    else:
        body = {'repository_version': version_href}
    client = api.Client(cfg, api.json_handler)
    call_report = client.post(urljoin(publisher['_href'], 'publish/'), body)
    # As of this writing, Pulp 3 only returns one task. If Pulp 3 starts
    # returning multiple tasks, this may need to be re-written.
    tasks = tuple(api.poll_spawned_tasks(cfg, call_report))
    if len(tasks) != 1:
        message = (
            'Multiple tasks were spawned in response to API call. This is '
            'unexpected, and Pulp Smash may handle the response incorrectly. '
            'Here is the tasks generated: {}'
        )
        message = message.format(tasks)
        warnings.warn(message, RuntimeWarning)
    return client.get(tasks[-1]['created_resources'][0])


def _build_content_fetcher(content_field):
    """Build closure for fetching content from a repository.

    :param content_field: The name of a field on a RepositoryVersion, which
        contains a dict of content types and the URL at which to view content.
    :returns: A closure which returns content from the specified field.
    """
    def inner(repo, version_href=None):
        """Read the content units of a given repository.

        :param repo: A dict of information about the repository.
        :param version_href: The repository version to read. If none, read the
            latest repository version.
        :returns: A list of information about the content units present in a given
            repository version.
        """
        version_href = version_href or repo['_latest_version_href']

        if version_href is None:
            # Repository has no latest version, and therefore no content.
            return defaultdict(list)

        client = api.Client(config.get_config(), api.page_handler)
        repo_version = client.get(version_href)

        content = defaultdict(list)
        for content_type, content_url in repo_version[content_field].items():
            typed_content = client.get(content_url)
            content[content_type] = typed_content
        return content
    return inner


get_content = _build_content_fetcher('content_hrefs')  # pylint:disable=invalid-name
get_added_content = _build_content_fetcher('content_added_hrefs')  # pylint:disable=invalid-name
get_removed_content = _build_content_fetcher('content_removed_hrefs')  # pylint:disable=invalid-name


def _build_summary_fetcher(summary_field):
    """Build closure for fetching content summaries from a repository.

    :param content_field: The name of a field on a RepositoryVersion, which
        contains a dict of content types and their counts.
    :returns: A closure which returns content from the specified field.
    """
    def inner(repo, version_href=None):
        """Read the "content summary" of a given repository version.

        Repository versions have a "content_summary" which lists the content
        types and the number of units of that type present in the repo version.

        :param repo: A dict of information about the repository.
        :param version_href: The repository version to read. If none, read the
            latest repository version.
        :returns: The "content_summary" of the repo version.
        """
        version_href = version_href or repo['_latest_version_href']

        if version_href is None:
            # Repository has no latest version, and therefore no content.
            return {}

        client = api.Client(config.get_config(), api.page_handler)
        return client.get(version_href)[summary_field]
    return inner


get_content_summary = _build_summary_fetcher('content_summary')  # pylint:disable=invalid-name
get_added_content_summary = _build_summary_fetcher('content_added_summary')  # pylint:disable=invalid-name
get_removed_content_summary = _build_summary_fetcher('content_removed_summary')  # pylint:disable=invalid-name


def delete_orphans(cfg=None):
    """Clean all content units present in pulp.

    An orphaned artifact is an artifact that is not in any content units.
    An orphaned content unit is a content unit that is not in any repository
    version.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
     host.
    """
    if cfg is None:
        cfg = config.get_config()
    api.Client(cfg, api.safe_handler).delete(ORPHANS_PATH)


def get_versions(repo, params=None):
    """Return repository versions, sorted by version ID.

    :param repo: A dict of information about the repository.
    :param params: Dictionary or bytes to be sent in the query string. Used to
        filter which versions are returned.
    :returns: A sorted list of dicts of information about repository versions.
    """
    client = api.Client(config.get_config(), api.page_handler)
    versions = client.get(repo['_versions_href'], params=params)
    versions.sort(
        key=lambda version: int(urlsplit(version['_href']).path.split('/')[-2])
    )
    return versions


def get_artifact_paths(repo, version_href=None):
    """Return the paths of artifacts present in a given repository version.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read.
    :returns: A set with the paths of units present in a given repository.
    """
    # content['artifact'] consists of a file path and name.
    artifact_paths = set()
    for typed_content in get_content(repo, version_href).values():
        for content in typed_content:
            # some content types with 1-to-1 artifact-content relationship
            # override 'artifacts', but some plugins will still have multiple
            # artifacts for their content.
            if content.get('_artifact'):
                artifact_paths.add(content['_artifact'])
            else:
                for artifact in content.get('_artifacts'):
                    artifact_paths.add(artifact)
    return artifact_paths


def delete_version(repo, version_href=None):
    """Delete a given repository version.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version that should be
        deleted.
    :returns: A tuple. The tasks spawned by Pulp.
    """
    version_href = version_href or repo['_latest_version_href']

    if version_href is None:
        # Repository has no latest version.
        raise ValueError('No version exists to be deleted.')

    cfg = config.get_config()
    client = api.Client(cfg, api.json_handler)
    call_report = client.delete(version_href)
    # As of this writing, Pulp 3 only returns one task. If Pulp 3 starts
    # returning multiple tasks, this may need to be re-written.
    return tuple(api.poll_spawned_tasks(cfg, call_report))


def gen_distribution(**kwargs):
    """Return a semi-random dict for use in creating a Distribution."""
    data = {'base_path': utils.uuid4(), 'name': utils.uuid4()}
    data.update(kwargs)
    return data


def gen_publisher(**kwargs):
    """Return a semi-random dict for use in creating an Publisher."""
    data = {'name': utils.uuid4()}
    data.update(kwargs)
    return data


def gen_remote(url, **kwargs):
    """Return a semi-random dict for use in creating a Remote.

    :param url: The URL of an external content source.
    """
    data = {'name': utils.uuid4(), 'url': url}
    data.update(kwargs)
    return data


def gen_repo(**kwargs):
    """Return a semi-random dict for use in creating a Repository."""
    data = {'name': utils.uuid4()}
    data.update(kwargs)
    return data
