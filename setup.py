#!/usr/bin/env python
# coding=utf-8
"""A setuptools-based script for installing Pulp Smash.

For more information, see:

* https://packaging.python.org/en/latest/index.html
* https://docs.python.org/distutils/sourcedist.html
"""
from __future__ import unicode_literals

from setuptools import find_packages, setup  # prefer setuptools over distutils


with open('README.rst') as handle:
    LONG_DESCRIPTION = handle.read()


with open('VERSION') as handle:
    VERSION = handle.read().strip()


setup(
    name='pulp-smash',
    version=VERSION,
    description='A library for testing Pulp',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/PulpQE/pulp-smash',
    author='Jeremy Audet',
    author_email='ichimonji10@gmail.com',
    license='GPLv3',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        ('License :: OSI Approved :: GNU General Public License v3 or later '
         '(GPLv3+)'),
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    packages=find_packages(),
    install_requires=[
        'mock',
        'packaging',
        'plumbum',
        'python-dateutil',
        'pyxdg',
        'requests',
        'unittest2',
    ],
    test_suite='tests',
)
