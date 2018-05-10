#!/usr/bin/env python3
# coding=utf-8
"""A setuptools-based script for installing Pulp Smash.

For more information, see:

* https://packaging.python.org/en/latest/index.html
* https://docs.python.org/distutils/sourcedist.html
"""
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
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        ('License :: OSI Approved :: GNU General Public License v3 or later '
         '(GPLv3+)'),
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(include=['pulp_smash', 'pulp_smash.*']),
    install_requires=[
        'click',
        'jsonschema',
        'packaging',
        'plumbum',
        'python-dateutil',
        'pyxdg',
        'requests',
    ],
    extras_require={
        'dev': [
            # For `make lint`
            'flake8',
            'flake8-docstrings',
            'flake8-quotes',
            'pydocstyle',
            'pylint',
            # For `make test-coverage`
            'coveralls',
            # For `make docs-html` and `make docs-clean`
            'sphinx',
            # For `make package`
            'wheel',
            # For `make publish`
            'twine',
        ],
    },
    entry_points={
        'console_scripts': ['pulp-smash=pulp_smash.pulp_smash_cli:pulp_smash'],
    },
    test_suite='tests',
)
