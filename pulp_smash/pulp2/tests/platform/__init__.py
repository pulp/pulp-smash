# coding=utf-8
"""Functional tests for the Pulp platform.

According to the documentation:

    Pulp can be viewed as consisting of two parts, the platform (which includes
    both the server and client applications) and plugins (which provide support
    for a particular set of content types).

This package contains tests for the Pulp platform. These tests target
plugin-agnostic functionality. These tests should not rely on any
plugin-specific functionality, such as the ability to work with RPMs or ISOs.
"""
