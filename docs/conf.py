# coding=utf-8
"""Sphinx documentation generator configuration file.

The full set of configuration options is listed on the Sphinx website:
http://sphinx-doc.org/config.html
"""
import os
import re
import sys
from packaging.version import Version


# Add the Pulp Smash root directory to the system path. This allows references
# such as :mod:`pulp_smash.whatever` to be processed correctly.
ROOT_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    os.path.pardir
))
sys.path.insert(0, ROOT_DIR)

# We pass the raw version string to Version() to ensure it is compliant with
# PEP 440. An InvalidVersion exception is raised if the version is
# non-conformant, so the act of generating documentation serves as a unit test
# for the contents of the `VERSION` file.
#
# We use the raw version string when generating documentation for the sake of
# human friendliness: the meaning of '2016.02.18' is presumably more intuitive
# than the meaning of '2016.2.18'. The regex enforcing this format allows
# additional segments. This is done to allow multiple releases in a single day.
# For example, 2016.02.18.3 is the fourth release in a given day.
with open(os.path.join(ROOT_DIR, 'VERSION')) as handle:
    VERSION = handle.read().strip()
    Version(VERSION)
    assert re.match(r'\d{4,4}(\.\d\d){2,2}', VERSION) is not None


# Project Information ---------------------------------------------------------
# pylint:disable=invalid-name
author = 'Pulp QE'
copyright = '2015, Pulp QE'  # pylint:disable=redefined-builtin
project = 'Pulp Smash'
version = release = VERSION


# General Configuration -------------------------------------------------------
extensions = ['sphinx.ext.autodoc']
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build']
nitpicky = True
autodoc_default_flags = ['members']


# Format-Specific Options -----------------------------------------------------
htmlhelp_basename = 'PulpSmashdoc'
latex_documents = [(
    master_doc,
    project + '.tex',
    project + ' Documentation',
    author,
    'manual'
)]
man_pages = [(
    master_doc,
    'pulp-smash',
    project + ' Documentation',
    ['Pulp QE'],
    1  # man pages section
)]
texinfo_documents = [(
    master_doc,
    'PulpSmash',
    project + ' Documentation',
    author,
    'PulpSmash',
    ('Pulp Smash is a Python library that facilitates functional testing of '
     'Pulp.'),
    'Miscellaneous'
)]
