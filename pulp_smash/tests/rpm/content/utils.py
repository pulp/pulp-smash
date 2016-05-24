# coding=utf-8

"""Utils for rwr tests."""

from collections import namedtuple
import contextlib
import gzip
import tempfile


def ensure_required(path, required_fields, ret, source):
    """ensure required fields always present in diff output."""
    if not required_fields:
        return
    str_path = '.'.join(path)
    if str_path in required_fields:
        path = required_fields[str_path]
        if path not in ret or not path:
            ret[path] = source[path]


def cmp_list_object(diff_setup):
    """Compare two lists."""
    for index in range(max(len(diff_setup.elem1), len(diff_setup.elem2))):
        diff_setup.e_ret.append(None)
        if index >= len(diff_setup.elem1):
            label = 'MISSING_IN_%s' % diff_setup.d1name
            diff_setup.e_ret[index] = {label: diff_setup.elem2[index]}
            ensure_required(diff_setup.path1, diff_setup.required_fields,
                            diff_setup.e_ret[index], diff_setup.elem2[index])
        elif index >= len(diff_setup.elem2):
            label = 'MISSING_IN_%s' % diff_setup.d2name
            diff_setup.e_ret[index] = {label: diff_setup.elem1[index]}
            ensure_required(diff_setup.path1, diff_setup.required_fields,
                            diff_setup.e_ret[index], diff_setup.elem1[index])
        else:
            diff_setup.stack1.insert(0, (diff_setup.elem1[index],
                                         diff_setup.path1))
            diff_setup.stack2.insert(0, (diff_setup.elem2[index],
                                         diff_setup.path2))
            if isinstance(diff_setup.elem1[index], list) and\
               isinstance(diff_setup.elem2[index], list):
                diff_setup.e_ret[index] = []
            else:
                diff_setup.e_ret[index] = {}
            diff_setup.ret_stack.insert(0, (diff_setup.e_ret, index,
                                            diff_setup.e_ret[index]))


def cmp_dict_object(diff_setup):
    """Compare two dicts."""
    if not diff_setup.d1name:
        diff_setup.d1name = '1'
    if not diff_setup.d2name:
        diff_setup.d2name = '2'
    for key in set(diff_setup.elem1.keys() + diff_setup.elem2.keys()):
        if key in diff_setup.elem1 and key in diff_setup.elem2:
            diff_setup.stack1.insert(0, (diff_setup.elem1[key],
                                         diff_setup.path1 + [key]))
            diff_setup.stack2.insert(0, (diff_setup.elem2[key],
                                         diff_setup.path2 + [key]))
            if isinstance(diff_setup.elem1[key], list) and\
               isinstance(diff_setup.elem2[key], list):
                diff_setup.e_ret[key] = []
            elif key not in diff_setup.e_ret:
                diff_setup.e_ret[key] = {}
            diff_setup.ret_stack.insert(0, (diff_setup.e_ret, key,
                                            diff_setup.e_ret[key]))
            ensure_required(diff_setup.path1, diff_setup.required_fields,
                            diff_setup.e_ret, diff_setup.elem2)
        else:
            if key not in diff_setup.elem1:
                label = 'MISSING_IN_%s' % diff_setup.d1name
                diff_setup.e_ret[key] = {label: diff_setup.elem2[key]}
                ensure_required(diff_setup.path1, diff_setup.required_fields,
                                diff_setup.e_ret, diff_setup.elem2)
            else:
                label = 'MISSING_IN_%s' % diff_setup.d2name
                diff_setup.e_ret[key] = {label: diff_setup.elem1[key]}
                ensure_required(diff_setup.path1, diff_setup.required_fields,
                                diff_setup.e_ret, diff_setup.elem1)


def remove_empty(ret):
    """remove empty items from diff result."""
    ret_stack = [(None, '', ret)]
    while ret_stack:
        (e_parent, e_key, e_ret) = ret_stack.pop(0)
        if not e_ret:
            e_parent.pop(e_key)
        if isinstance(e_ret, dict):
            for key, val in e_ret.iteritems():
                ret_stack.insert(0, (e_ret, key, val))
        if isinstance(e_ret, list):
            for index, _ in enumerate(e_ret):
                ret_stack.insert(0, (e_ret, index, e_ret[index]))


def isstring(obj):
    """Check if obj is string."""
    try:
        return isinstance(obj, basestring)
    except NameError:
        return isinstance(obj, str)


def dict_cmp(dict1, dict2, d1name, d2name, required_fields=None):
    """Compare two dictionaries and return the diff."""
    ret = {}
    e_ret_setup = namedtuple('RetStackItem', ['e_parent', 'e_index', 'e_ret'])
    ret_stack = [e_ret_setup(None, None, ret)]
    dstacks = {'stack1': [(dict1, [])],
               'stack2': [(dict2, [])]}
    diff_setup = namedtuple('DiffSetup',
                            ['elem1', 'elem2', 'e_ret', 'stack1', 'stack2',
                             'ret_stack', 'path1', 'path2', 'required_fields',
                             'd1name', 'd2name'])

    while dstacks['stack1'] and dstacks['stack2']:
        elem1, path1 = dstacks['stack1'].pop(0)
        elem2, path2 = dstacks['stack2'].pop(0)
        e_ret_tuple = ret_stack.pop(0)

        if elem1 != elem2:
            if elem1.__class__ != elem2.__class__ \
               and not (isstring(elem1) and isstring(elem2)):
                e_ret_tuple['__TYPE_%s__' % d1name] = str(type(elem1))
                e_ret_tuple['__TYPE_%s__' % d2name] = str(type(elem2))
                ensure_required(path1, required_fields,
                                e_ret_tuple.e_ret, elem1)
            elif isinstance(elem1, dict):
                cmp_dict_object(diff_setup(elem1, elem2, e_ret_tuple.e_ret,
                                           dstacks['stack1'],
                                           dstacks['stack2'],
                                           ret_stack, path1, path2,
                                           required_fields, d1name, d2name))
            elif isinstance(elem1, list):
                cmp_list_object(diff_setup(elem1, elem2, e_ret_tuple.e_ret,
                                           dstacks['stack1'],
                                           dstacks['stack2'],
                                           ret_stack, path1, path2,
                                           required_fields, d1name, d2name))
            else:
                if not isinstance(e_ret_tuple.e_ret, dict):
                    e_ret_tuple.e_ret = {}
                    e_ret_tuple.e_parent[e_ret_tuple.e_parent_index] = \
                        e_ret_tuple.e_ret
                e_ret_tuple.e_ret['MISSING_IN_%s' % d1name] = elem2
                e_ret_tuple.e_ret['MISSING_IN_%s' % d2name] = elem1
    if not ret:
        return ret

    remove_empty(ret)
    return ret


@contextlib.contextmanager
def open_gzipped(filehandle):
    """
    open gzip file.

    Extract gzip file into tmp filename and provide file pointer to the file.
    """
    tmp_file = tempfile.NamedTemporaryFile()
    try:
        tmp_file.write(filehandle.read())
        tmp_file.flush()
        gz_file = gzip.open(tmp_file.name)
        yield gz_file
        gz_file.close()
    finally:
        tmp_file.close()
