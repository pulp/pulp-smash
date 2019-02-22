# coding=utf-8
"""Sphinx documentation generator configuration file.

The full set of configuration options is listed on the Sphinx website:
http://sphinx-doc.org/config.html
"""
import os
import sys
from packaging.version import Version


# Add the Pulp Smash root directory to the system path. This allows references
# such as :mod:`pulp_smash.whatever` to be processed correctly.
ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.pardir)
)
sys.path.insert(0, ROOT_DIR)

# We pass the raw version string to Version() to ensure it is compliant with
# PEP 440. An InvalidVersion exception is raised if the version is
# non-conformant, so the act of generating documentation serves as a unit test
# for the contents of the `VERSION` file.
with open(os.path.join(ROOT_DIR, "VERSION")) as handle:
    VERSION = handle.read().strip()
    Version(VERSION)


# Project Information ---------------------------------------------------------
# pylint:disable=invalid-name
author = "Pulp QE"
copyright = "2015, Pulp QE"  # pylint:disable=redefined-builtin
project = "Pulp Smash"
version = release = VERSION


# General Configuration -------------------------------------------------------
extensions = ["sphinx.ext.autodoc"]
source_suffix = ".rst"
master_doc = "index"
exclude_patterns = ["_build"]
nitpicky = True
nitpick_ignore = [("py:class", "type")]
autodoc_default_flags = ["members", "show-inheritance", "undoc-members"]
# Format-Specific Options -----------------------------------------------------
htmlhelp_basename = "PulpSmashdoc"
latex_documents = [
    (
        master_doc,
        project + ".tex",
        project + " Documentation",
        author,
        "manual",
    )
]
man_pages = [
    (
        master_doc,
        "pulp-smash",
        project + " Documentation",
        [author],
        1,  # man pages section
    )
]
texinfo_documents = [
    (
        master_doc,
        "PulpSmash",
        project + " Documentation",
        author,
        "PulpSmash",
        (
            "Pulp Smash is a Python library that facilitates functional testing of "
            "Pulp."
        ),
        "Miscellaneous",
    )
]
