# coding=utf-8
"""Utilities for RPM tests."""
import os
from functools import partial
from io import StringIO
from unittest import SkipTest

from packaging.version import Version

from pulp_smash import cli, selectors
from pulp_smash.pulp2 import utils as pulp2_utils


def set_up_module():
    """Skip tests if Pulp 2 isn't under test or if RPM isn't installed."""
    pulp2_utils.require_pulp_2(SkipTest)
    pulp2_utils.require_issue_3159(SkipTest)
    pulp2_utils.require_issue_3687(SkipTest)
    pulp2_utils.require_unit_types({'rpm'}, SkipTest)


def check_issue_2277(cfg):
    """Return true if `Pulp #2277`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2277: https://pulp.plan.io/issues/2277
    """
    if (cfg.pulp_version >= Version('2.10') and
            not selectors.bug_is_fixed(2277, cfg.pulp_version)):
        return True
    return False


def check_issue_2387(cfg):
    """Return true if `Pulp #2387`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2387: https://pulp.plan.io/issues/2387
    """
    if (cfg.pulp_version >= Version('2.10') and os_is_rhel6(cfg) and
            not selectors.bug_is_fixed(2387, cfg.pulp_version)):
        return True
    return False


def check_issue_2354(cfg):
    """Return true if `Pulp #2354`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2354: https://pulp.plan.io/issues/2354
    """
    if (cfg.pulp_version >= Version('2.10') and
            not selectors.bug_is_fixed(2354, cfg.pulp_version)):
        return True
    return False


def check_issue_2620(cfg):
    """Return true if `Pulp #2620`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2620: https://pulp.plan.io/issues/2620
    """
    if (cfg.pulp_version >= Version('2.12') and
            not selectors.bug_is_fixed(2620, cfg.pulp_version)):
        return True
    return False


def check_issue_2798(cfg):
    """Return true if `Pulp #2798`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2798: https://pulp.plan.io/issues/2798
    """
    return (cfg.pulp_version >= Version('2.14') and
            not selectors.bug_is_fixed(2798, cfg.pulp_version))


def check_issue_2844(cfg):
    """Return true if `Pulp #2844`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #2844: https://pulp.plan.io/issues/2844
    """
    return (cfg.pulp_version >= Version('2.14') and
            not selectors.bug_is_fixed(2844, cfg.pulp_version))


def check_issue_3104(cfg):
    """Return true if `Pulp #3104`_ affects the targeted Pulp system.

    :param pulp_smash.config.PulpSmashConfig cfg: The Pulp system under test.

    .. _Pulp #3104: https://pulp.plan.io/issues/3104
    """
    return (cfg.pulp_version >= Version('2.15') and
            not selectors.bug_is_fixed(3104, cfg.pulp_version))


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
            'echo "{}" | {}tee {} > /dev/null'.format(
                section.getvalue(),
                '' if cli.is_root(cfg) else 'sudo ',
                path
            )
        )
    return path


skip_if = partial(selectors.skip_if, exc=SkipTest)  # pylint:disable=invalid-name
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
