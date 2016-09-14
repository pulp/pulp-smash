#!/usr/bin/env python3
# coding=utf-8
"""Run the entire suite of functional Pulp Smash tests.

This script exists so that cProfile may be used to collect profiling
information while Pulp Smash runs. A typical use case is the following::

    python -m cProfile -o run.prof scripts/run_functional_tests.py
    gprof2dot -f pstats run.prof | dot -Tsvg -o run.svg

This requires that gprof2dot and GraphViz be installed. The former is available
via PyPi, and the latter must be installed on your system.
"""
import unittest


def main():
    """Find and execute test cases."""
    # discover() searches for test cases within a *package*. Even if pointed at
    # a module, it will go up a level and search through the parent package.
    # One can select a module with e.g. `pattern='test_login.py'`.
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().discover('pulp_smash.tests'))
    runner = unittest.TextTestRunner()
    runner.run(suite)


if __name__ == '__main__':
    exit(main())
