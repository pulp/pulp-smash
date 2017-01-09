# coding=utf-8
"""Tests to verify that Pulp has proper SELinux permissions."""
import re
import unittest
from collections import namedtuple

from pulp_smash import cli, config, selectors, utils


CELERY_LABEL = ':system_r:celery_t:s0'
"""A label commonly applied to celery processes.

The "user" segment of the label is intentionally omitted, as it is known to
vary. See `Pulp Smash #444 (comment)
<https://github.com/PulpQE/pulp-smash/issues/444#issuecomment-265798957>`_.
"""

HTTPD_LABEL = ':system_r:httpd_t:s0'
"""A label commonly applied to httpd processes.

The "user" segment of the label is intentionally omitted, as it is known to
vary. See `Pulp Smash #444 (comment)
<https://github.com/PulpQE/pulp-smash/issues/444#issuecomment-265798957>`_.
"""

PS_FIELDS = ('label', 'args')
"""The fields that ``ps`` should display. See ``man ps`` for details."""

Process = namedtuple('Process', PS_FIELDS)
"""A single line of output from ``ps``."""


class ProcessLabelsTestCase(unittest.TestCase):
    """Test that Pulp processes have correct SELinux labels.

    This test case targets `Pulp Smash #444
    <https://github.com/PulpQE/pulp-smash/issues/444>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Get all of the processes running on the target Pulp system."""
        cfg = config.get_config()
        cmd = [] if utils.is_root(config.get_config()) else ['sudo']
        cmd.extend(('ps', '-A', '-w', '-w', '-o', ','.join(PS_FIELDS)))
        cls.procs = [
            Process(*line.split(maxsplit=1))
            for line in cli.Client(cfg).run(cmd).stdout.splitlines()
        ]

    def _do_test(self, label, arg):
        """Assert that certain processes have a label of ``label``.

        Select all processes that were invoked with an argument string
        containing ``arg``. Assert that at least one such process exists, and
        that all such processes have a label of ``label``.
        """
        procs = [proc for proc in self.procs if arg in proc.args]
        self.assertGreater(len(procs), 0, arg)
        for proc in procs:
            # Don't use subTest here. Doing so destroys traceback information
            # and leads to distractingly verbose output.
            self.assertEqual(proc.label[proc.label.find(':'):], label, procs)

    def test_httpd(self):
        """Verify the labels of the ``wsgi:pulp*`` processes.

        They should have a label of :data:`HTTPD_LABEL`.
        """
        self._do_test(HTTPD_LABEL, 'wsgi:pulp')

    def test_resource_manager(self):
        """Verify the labels of the ``resource_manager`` processes.

        They should have a label of :data:`CELERY_LABEL`.
        """
        self._do_test(CELERY_LABEL, 'resource_manager')

    def test_reserved_resource_worker_0(self):
        """Verify the labels of the ``reserved_resource_worker-0`` processes.

        They should have a label of :data:`CELERY_LABEL`.
        """
        self._do_test(CELERY_LABEL, 'reserved_resource_worker-0')

    def test_celerybeat(self):
        """Verify the label of the Pulp celerybeat process.

        It should have a label of :data:`CELERY_LABEL`.
        """
        # Pulp celerybeat is invoked as `/usr/bin/python /usr/bin/celery beat
        # [arguments]`. If this simple approach fails, a more robust approach
        # is to use a regex that searches for 'celery[:space:]+beat'.
        self._do_test(CELERY_LABEL, 'celery beat')


class FileLabelsTestCase(unittest.TestCase):
    """Test that files have correct SELinux labels.

    This test case targets `Pulp Smash #442
    <https://github.com/PulpQE/pulp-smash/issues/442>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create a CLI client."""
        cls.client = cli.Client(config.get_config())
        cls.file_matcher = re.compile(r'^# file: (\S+)')
        cls.label_matcher = re.compile(r'^security\.selinux="([\w:]+)"$')

    def _do_test(self, file_, label, recursive=False):
        """Assert that certain files have a label of ``label``.

        Get the SELinux label of the given ``file_``, or all files rooted at
        ``file_` if ``recursive`` is true. For each SELinux label, strip off
        the leading "user" portion of the label, and assert that the result — a
        string in the form :role:type:level — has the given ``label``.
        """
        # Typical output:
        #
        #     # getfattr --name=security.selinux /etc/passwd
        #     getfattr: Removing leading '/' from absolute path names
        #     # file: etc/passwd
        #     security.selinux="system_u:object_r:passwd_file_t:s0"
        #
        cmd = [] if utils.is_root(config.get_config()) else ['sudo']
        cmd.extend(('getfattr', '--name=security.selinux'))
        if recursive:
            cmd.append('--recursive')
        cmd.append(file_)
        lines = self.client.run(cmd).stdout.splitlines()
        matches = 0
        getfattr_file = None  # tracks file currently under consideration
        for line in lines:

            match = self.file_matcher.match(line)
            if match is not None:
                getfattr_file = match.groups(1)
                continue

            match = self.label_matcher.match(line)
            if match is not None:
                matches += 1
                # Strip "user" prefix from label. For example:
                # user:role:type:level → :role:type:level
                file_label = match.group(1)
                file_label = file_label[file_label.find(':'):]
                self.assertEqual(file_label, label, getfattr_file)

        self.assertGreater(matches, 0, lines)

    def test_pulp_celery_fc(self):
        """Test files listed in ``pulp-celery.fc``."""
        with self.subTest():
            self._do_test('/usr/bin/celery', ':object_r:celery_exec_t:s0')
        with self.subTest():
            self._do_test(
                '/var/cache/pulp',
                ':object_r:pulp_var_cache_t:s0',
                True,
            )
        with self.subTest():
            self._do_test('/var/run/pulp', ':object_r:pulp_var_run_t:s0', True)

    def test_pulp_server_fc(self):
        """Test files listed in ``pulp-server.fc``."""
        files_labels = [
            ('/etc/pki/pulp', ':object_r:pulp_cert_t:s0'),
            ('/etc/pulp', ':object_r:httpd_sys_content_t:s0'),
            ('/usr/share/pulp/wsgi', ':object_r:httpd_sys_content_t:s0'),
            ('/var/log/pulp', ':object_r:httpd_sys_rw_content_t:s0'),
        ]
        if selectors.bug_is_testable(2508, config.get_config().version):
            files_labels.append(
                ('/var/lib/pulp', ':object_r:httpd_sys_rw_content_t:s0')
            )
        for file_, label in files_labels:
            with self.subTest((file_, label)):
                self._do_test(file_, label, True)

    def test_pulp_streamer_fc(self):
        """Test files listed in ``pulp-streamer.fc``."""
        self._do_test('/usr/bin/pulp_streamer', ':object_r:streamer_exec_t:s0')
