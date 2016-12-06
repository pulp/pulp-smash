# coding=utf-8
"""Tests to verify that Pulp has proper SELinux permissions."""
import unittest
from collections import namedtuple

from pulp_smash import cli, config, utils


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
        cmd = ['ps', '-A', '-w', '-w', '-o', ','.join(PS_FIELDS)]
        if not utils.is_root(cfg):
            cmd.insert(0, 'sudo')
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
