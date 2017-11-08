# coding=utf-8
"""Utilities for RPM tests."""
import os
from io import StringIO

from packaging.version import Version

from pulp_smash import cli, selectors, utils
from pulp_smash.utils import is_root


def set_up_module():
    """Skip tests if the RPM plugin is not installed.

    See :mod:`pulp_smash.tests` for more information.
    """
    utils.set_up_module()
    utils.skip_if_type_is_unsupported('rpm')


def check_issue_2277(cfg):
    """Return true if `Pulp #2277`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2277: https://pulp.plan.io/issues/2277
    """
    if (cfg.pulp_version >= Version('2.10') and
            selectors.bug_is_untestable(2277, cfg.pulp_version)):
        return True
    return False


def check_issue_2387(cfg):
    """Return true if `Pulp #2387`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2387: https://pulp.plan.io/issues/2387
    """
    if (cfg.pulp_version >= Version('2.10') and os_is_rhel6(cfg) and
            selectors.bug_is_untestable(2387, cfg.pulp_version)):
        return True
    return False


def check_issue_2354(cfg):
    """Return true if `Pulp #2354`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2354: https://pulp.plan.io/issues/2354
    """
    if (cfg.pulp_version >= Version('2.10') and
            selectors.bug_is_untestable(2354, cfg.pulp_version)):
        return True
    return False


def check_issue_2620(cfg):
    """Return true if `Pulp #2620`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2620: https://pulp.plan.io/issues/2620
    """
    if (cfg.pulp_version >= Version('2.12') and
            selectors.bug_is_untestable(2620, cfg.pulp_version)):
        return True
    return False


def check_issue_2798(cfg):
    """Return true if `Pulp #2798`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2798: https://pulp.plan.io/issues/2798
    """
    return (cfg.pulp_version >= Version('2.14') and
            selectors.bug_is_untestable(2798, cfg.pulp_version))


def check_issue_2844(cfg):
    """Return true if `Pulp #2844`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2844: https://pulp.plan.io/issues/2844
    """
    return (cfg.pulp_version >= Version('2.14') and
            selectors.bug_is_untestable(2844, cfg.pulp_version))


def check_issue_3104(cfg):
    """Return true if `Pulp #3104`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #3104: https://pulp.plan.io/issues/3104
    """
    return (cfg.pulp_version >= Version('2.15') and
            selectors.bug_is_untestable(3104, cfg.pulp_version))


def os_is_rhel6(cfg):
    """Return ``True`` if the server runs RHEL 6, or ``False`` otherwise.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the system
        being targeted.
    :returns: True or false.
    """
    response = cli.Client(cfg, cli.echo_handler).run((
        'grep',
        '-i',
        'red hat enterprise linux server release 6',
        '/etc/redhat-release',
    ))
    return response.returncode == 0


def gen_yum_config_file(cfg, repositoryid, **kwargs):
    """Generate a yum configuration file and write it to ``/etc/yum.repos.d/``.

    Generate a yum configuration file containing a single repository section,
    and write it to ``/etc/yum.repos.d/{repositoryid}.repo``.

    :param pulp_smash.config.PulpSmashConfig cfg: The system on which to create
        a yum configuration file.
    :param repositoryid: The section's ``repositoryid``. Used when naming the
        configuration file and populating the brackets at the head of the file.
        For details, see yum.conf(5).
    :param kwargs: Section options. Each kwarg corresponds to one option. For
        details, see yum.conf(5).
    :returns: The path to the yum configuration file.
    """
    path = os.path.join('/etc/yum.repos.d/', repositoryid + '.repo')
    with StringIO() as section:
        section.write('[{}]\n'.format(repositoryid))
        for key, value in kwargs.items():
            section.write('{}: {}\n'.format(key, value))
        cli.Client(cfg).machine.session().run(
            'echo "{}" | {}tee {} > /dev/null'
            .format(section.getvalue(), '' if is_root(cfg) else 'sudo ', path)
        )
    return path


def get_rpm_names_versions(server_config, repo_id):
    """Get a dict of repo's RPMs with names as keys, mapping to version lists.

    :param pulp_smash.config.PulpSmashConfig server_config: Information about
        the Pulp deployment being targeted.
    :param repo_id: A RPM repository ID.
    :returns: The name and versions of each package in the repository, with the
        versions sorted in ascending order. For example: ``{'walrus': ['0.71',
        '5.21']}``.
    """
    keyword = 'Filename:'
    completed_proc = cli.Client(server_config).run(
        'pulp-admin rpm repo content rpm --repo-id {}'.format(repo_id).split()
    )
    rpms = {}
    for line in completed_proc.stdout.splitlines():
        if keyword not in line:
            continue
        # e.g. 'Filename: my-walrus-0.71-1.noarch.rpm ' → ['my-walrus', '0.71']
        filename_parts = line.lstrip(keyword).strip().split('-')[:-1]
        name = '-'.join(filename_parts[:-1])
        version = filename_parts[-1]
        rpms.setdefault(name, []).append(version)
    for rpm in rpms:
        rpms[rpm] = sorted(rpms[rpm], key=Version)
    return rpms
