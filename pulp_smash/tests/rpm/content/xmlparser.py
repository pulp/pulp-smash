# coding=utf-8
# pylint: disable=no-member

"""Expat general xml parser.

This modules provides Parser class that serves for parsing XML elements.
Output of parse_* methods is dictonary that contains parsed XML structure.
Because parser class is designed as general parser, it doesn't include
any logic of data processing. There are only 3 rules that are applied
on data processing:
1. <element>text</element> is parsed as {"element":{".cdata": text}}
2. <element attribute="value"></element> is parsed as
{"element":{"attribute":"value"}}
3. <element><item>1</item><item>2</item><element> is parsed as
{"element":{"item":[{".cdata":"1"}, {".cdata":"2"}]}}

"""

try:
    import StringIO
except ImportError:
    import io as StringIO

import xml.parsers.expat
import re


class UnknownElementError(Exception):
    """UnkownElement exeption."""

    def __init__(self, name):
        """init the exception with name."""
        super(UnknownElementError, self).__init__()
        self.name = name

    def __repr__(self):
        """repr for exception."""
        return 'UnknownElementError: element "%s"' % self.name

    def __str__(self):
        """str for exception."""
        return 'UnknownXMLStructureError: path "%s"' % self.name


class UnknownXMLStructureError(Exception):
    """UnkownXMLStructure exeption."""

    def __init__(self, path):
        """init the exception with path."""
        super(UnknownXMLStructureError, self).__init__()
        self.path = path

    def __repr__(self):
        """repr for exception."""
        return 'UnknownXMLStructureError: path "%s"' % self.path

    def __str__(self):
        """str for exception."""
        return 'UnknownXMLStructureError: path "%s"' % self.path


class Parser(object):
    """XML expat parser."""

    def __init__(self):
        """Initialize the parser."""
        self.parser = xml.parsers.expat.ParserCreate()
        self.parser.StartElementHandler = self.start_el_handler
        self.parser.EndElementHandler = self.end_el_handler
        self.parser.CharacterDataHandler = self.char_data_handler
        self.path = ''
        self.tree = {}
        self.el_stack = [self.tree]
        self.cdata = False
        self.source = None
        self.indent = ''

    def start_el_handler(self, name, attrs):
        """Handler called when new element is found on input."""
        parent = self.el_stack[0]
        new_el = {}
        for attr_key, attr_val in attrs.iteritems():
            new_el[attr_key] = attr_val

        self.el_stack.insert(0, new_el)
        if isinstance(parent, list):
            parent.append(new_el)
        elif isinstance(parent, dict):
            if name in parent:
                if isinstance(parent[name], list):
                    parent[name].append(new_el)
                else:
                    old = parent[name]
                    parent[name] = [old]
                    parent[name].append(new_el)
            else:
                parent[name] = new_el
        self.cdata = False

    def end_el_handler(self, name):
        """Handler called when end of element is found on input."""
        del name  # unused
        self.cdata = False
        parent = self.el_stack.pop(0)
        if '.cdata' in parent:
            parent['.cdata'] = parent['.cdata'].rstrip(' ')

    def char_data_handler(self, text):
        """Handler called when text data is found on input."""
        if not self.cdata:
            self.indent = re.match(r"^\s*", text).group()
            self.cdata = True
        parent = self.el_stack[0]
        stripped = re.sub(self.indent, '', text)
        if '.cdata' in parent:
            parent['.cdata'] = '%s%s' % (parent['.cdata'], stripped)
        else:
            parent['.cdata'] = stripped

    def parse_file(self, filename):
        """Parse XML filename."""
        self.source = filename
        self.parser.ParseFile(filename)
        return self.tree

    def parse_str(self, _str):
        """Parse XML in string."""
        self.source = StringIO.StringIO(_str)
        self.parser.Parse(_str, True)
        return self.tree
