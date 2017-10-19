# coding=utf-8
"""Utility functions for docker CLI tests.

All of the functions in this module share a common structure. The first
argument is a :class:`pulp_smash.config.PulpSmashConfig`, and all other
arguments correspond to command-line options. Most arguments are named after a
flag. For example, an argument ``to_repo_id`` corresponds to the flag
``--to-repo-id``.

For the meaning of each argument, see pulp-admin.
"""
from pulp_smash import cli


def repo_copy(server_config, unit_type, from_repo_id=None, to_repo_id=None):
    """Execute ``pulp-admin docker repo copy {unit_type}``."""
    cmd = 'pulp-admin docker repo copy {}'.format(unit_type).split()
    if from_repo_id is not None:
        cmd.extend(('--from-repo-id', from_repo_id))
    if to_repo_id is not None:
        cmd.extend(('--to-repo-id', to_repo_id))
    return cli.Client(server_config).run(cmd)


def repo_create(  # pylint:disable=too-many-arguments
        server_config,
        enable_v1=None,
        enable_v2=None,
        feed=None,
        repo_id=None,
        repo_registry_id=None,
        upstream_name=None):
    """Execute ``pulp-admin docker repo create``."""
    cmd = 'pulp-admin docker repo create'.split()
    if enable_v1 is not None:
        cmd.extend(('--enable-v1', enable_v1))
    if enable_v2 is not None:
        cmd.extend(('--enable-v2', enable_v2))
    if feed is not None:
        cmd.extend(('--feed', feed))
    if repo_id is not None:
        cmd.extend(('--repo-id', repo_id))
    if repo_registry_id is not None:
        cmd.extend(('--repo-registry-id', repo_registry_id))
    if upstream_name is not None:
        cmd.extend(('--upstream-name', upstream_name))
    return cli.Client(server_config).run(cmd)


def repo_delete(server_config, repo_id):
    """Execute ``pulp-admin docker repo delete``."""
    cmd = 'pulp-admin docker repo delete --repo-id {}'.format(repo_id).split()
    return cli.Client(server_config).run(cmd)


def repo_list(server_config, repo_id=None, details=False):
    """Execute ``pulp-admin docker repo list``."""
    cmd = 'pulp-admin docker repo list'.split()
    if repo_id is not None:
        cmd.extend(('--repo-id', repo_id))
    if details:
        cmd.append('--details')
    return cli.Client(server_config).run(cmd)


def repo_search(server_config, unit_type, fields=None, repo_id=None):
    """Execute ``pulp-admin docker repo search {unit_type}``."""
    cmd = 'pulp-admin docker repo search {}'.format(unit_type).split()
    if fields is not None:
        cmd.extend(('--fields', fields))
    if repo_id is not None:
        cmd.extend(('--repo-id', repo_id))
    return cli.Client(server_config).run(cmd)


def repo_sync(server_config, repo_id):
    """Execute ``pulp-admin docker repo sync run``."""
    cmd = 'pulp-admin docker repo sync run'.split()
    cmd.extend(('--repo-id', repo_id))
    return cli.Client(server_config).run(cmd)


def repo_update(  # pylint:disable=too-many-arguments
        server_config,
        enable_v1=None,
        enable_v2=None,
        feed=None,
        repo_id=None,
        upstream_name=None,
        repo_registry_id=None):
    """Execute ``pulp-admin docker repo update``."""
    cmd = 'pulp-admin docker repo update'.split()
    if enable_v1 is not None:
        cmd.extend(('--enable-v1', enable_v1))
    if enable_v2 is not None:
        cmd.extend(('--enable-v2', enable_v2))
    if feed is not None:
        cmd.extend(('--feed', feed))
    if repo_id is not None:
        cmd.extend(('--repo-id', repo_id))
    if upstream_name is not None:
        cmd.extend(('--upstream-name', upstream_name))
    if repo_registry_id is not None:
        cmd.extend(('--repo-registry-id', repo_registry_id))
    return cli.Client(server_config).run(cmd)


def repo_publish(server_config, repo_id, bg=None, force_full=None):  # noqa pylint:disable=invalid-name
    """Execute ``pulp-admin docker repo publish run``."""
    cmd = (
        'pulp-admin', 'docker', 'repo', 'publish', 'run', '--repo-id', repo_id
    )
    if bg:
        cmd += '--bg'
    if force_full:
        cmd += '--force-full'
    return cli.Client(server_config).run(cmd)
