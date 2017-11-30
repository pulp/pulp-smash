# coding=utf-8
"""Functional tests for the Pulp3 platform.

Pulp3 is composed by a core, aka called Pulp Core, and a Plugin API. Plugins
add support for a type of content to Pulp.

The Pulp Core does not manage any content itself. This functionality is
provided by its plugins, which use the Pulp Core Plugin API to manage specific
types of content, like RPM Packages or Puppet Modules

Platform namespace is composed by tests related to Pulp Core and File Plugin.
"""
