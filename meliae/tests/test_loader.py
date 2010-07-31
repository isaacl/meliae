# Copyright (C) 2009, 2010 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Read back in a dump file and process it"""

import gzip
import os
import sys
import tempfile

from meliae import (
    _loader,
    loader,
    scanner,
    tests,
    warn,
    )


# A simple dump, with a couple of cross references, etc.
# a@5 = 1
# b@4 = 2
# c@6 = 'a str'
# t@7 = (a, b)
# d@2 = {a:b, c:t}
# l@3 = [a, b]
# l.append(l)
# outer@1 = (d, l)
_example_dump = [
'{"address": 1, "type": "tuple", "size": 20, "len": 2, "refs": [2, 3]}',
'{"address": 3, "type": "list", "size": 44, "len": 3, "refs": [3, 4, 5]}',
'{"address": 5, "type": "int", "size": 12, "value": 1, "refs": []}',
'{"address": 4, "type": "int", "size": 12, "value": 2, "refs": []}',
'{"address": 2, "type": "dict", "size": 124, "len": 2, "refs": [4, 5, 6, 7]}',
'{"address": 7, "type": "tuple", "size": 20, "len": 2, "refs": [4, 5]}',
'{"address": 6, "type": "str", "size": 29, "len": 5, "value": "a str"'
 ', "refs": []}',
'{"address": 8, "type": "module", "size": 60, "name": "mymod", "refs": [2]}',
]

# Note that this doesn't have a complete copy of the references. Namely when
# you subclass object you get a lot of references, and type instances also
# reference other stuff that tends to chain to stuff like 'sys', which ends up
# referencing everything.
_instance_dump = [
'{"address": 1, "type": "MyClass", "size": 32, "refs": [2, 3]}',
'{"address": 3, "type": "type", "size": 452, "name": "MyClass", "refs": []}',
'{"address": 2, "type": "dict", "size": 140, "len": 4'
 ', "refs": [4, 5, 6, 7, 9, 10, 11, 12]}',
'{"address": 4, "type": "str", "size": 25, "len": 1, "value": "a", "refs": []}',
'{"address": 5, "type": "int", "size": 12, "value": 1, "refs": []}',
'{"address": 6, "type": "str", "size": 25, "len": 1, "value": "c", "refs": []}',
'{"address": 7, "type": "dict", "size": 140, "len": 1, "refs": [8, 6]}',
'{"address": 8, "type": "str", "size": 25, "len": 1, "value": "s", "refs": []}',
'{"address": 9, "type": "str", "size": 25, "len": 1, "value": "b", "refs": []}',
'{"address": 10, "type": "str", "size": 30, "len": 6'
 ', "value": "string", "refs": []}',
'{"address": 11, "type": "str", "size": 25, "len": 1, "value": "d", "refs": []}',
'{"address": 12, "type": "tuple", "size": 32, "len": 1, "refs": [13]}',
'{"address": 13, "type": "int", "size": 12, "value": 2, "refs": []}',
'{"address": 14, "type": "module", "size": 28, "name": "sys", "refs": [15]}',
'{"address": 15, "type": "dict", "size": 140, "len": 2, "refs": [5, 6, 9, 6]}',
]

_old_instance_dump = [
'{"address": 1, "type": "instance", "size": 36, "refs": [2, 3]}',
'{"address": 3, "type": "dict", "size": 140, "len": 2, "refs": [4, 5, 6, 7]}',
'{"address": 7, "type": "int", "size": 12, "value": 2, "refs": []}',
'{"address": 6, "type": "str", "size": 25, "len": 1, "value": "b", "refs": []}',
'{"address": 5, "type": "int", "size": 12, "value": 1, "refs": []}',
'{"address": 4, "type": "str", "size": 25, "len": 1, "value": "a", "refs": []}',
'{"address": 2, "type": "classobj", "size": 48, "name": "OldStyle"'
 ', "refs": [8, 43839680, 9]}',
'{"address": 9, "type": "str", "size": 32, "len": 8, "value": "OldStyle"'
 ', "refs": []}',
'{"address": 8, "type": "tuple", "size": 28, "len": 0, "refs": []}',
]

_intern_dict_dump = [
'{"address": 2, "type": "str", "size": 25, "len": 1, "value": "a", "refs": []}',
'{"address": 3, "type": "str", "size": 25, "len": 1, "value": "b", "refs": []}',
'{"address": 4, "type": "str", "size": 25, "len": 1, "value": "c", "refs": []}',
'{"address": 5, "type": "str", "size": 25, "len": 1, "value": "d", "refs": []}',
'{"address": 6, "type": "dict", "size": 512, "refs": [2, 5, 5, 5, 4, 4, 3, 3]}',
'{"address": 7, "type": "dict", "size": 512, "refs": [6, 6, 5, 5, 4, 4, 3, 3]}',
'{"address": 8, "type": "dict", "size": 512, "refs": [2, 2, 5, 5, 4, 4, 3, 3]}',
]


class TestLoad(tests.TestCase):

    def test_load_smoketest(self):
        test_dict = {1:2, None:'a string'}
        t = tempfile.TemporaryFile(prefix='meliae-')
        # On some platforms TemporaryFile returns a wrapper object with 'file'
        # being the real object, on others, the returned object *is* the real
        # file object
        t_file = getattr(t, 'file', t)
        scanner.dump_all_referenced(t_file, test_dict)
        t_file.seek(0)
        manager = loader.load(t_file, show_prog=False)
        test_dict_id = id(test_dict)
        self.assertTrue(test_dict_id in manager.objs,
			'%s not found in %s' % (test_dict_id, manager.objs.keys()))

    def test_load_one(self):
        objs = loader.load([
            '{"address": 1234, "type": "int", "size": 12, "value": 10'
            ', "refs": []}'], show_prog=False).objs
        keys = objs.keys()
        self.assertEqual([1234], keys)
        obj = objs[1234]
        self.assertTrue(isinstance(obj, _loader._MemObjectProxy))
        # The address should be exactly the same python object as the key in
        # the objs dictionary.
        self.assertTrue(keys[0] is obj.address)

    def test_load_without_simplejson(self):
        objs = loader.load([
            '{"address": 1234, "type": "int", "size": 12, "value": 10'
                ', "refs": []}',
            '{"address": 2345, "type": "module", "size": 60, "name": "mymod"'
                ', "refs": [1234]}',
            '{"address": 4567, "type": "str", "size": 150, "len": 126'
                ', "value": "Test \\\'whoami\\\'\\u000a\\"Your name\\"'
                ', "refs": []}'
            ], using_json=False, show_prog=False).objs
        keys = sorted(objs.keys())
        self.assertEqual([1234, 2345, 4567], keys)
        obj = objs[1234]
        self.assertTrue(isinstance(obj, _loader._MemObjectProxy))
        # The address should be exactly the same python object as the key in
        # the objs dictionary.
        self.assertTrue(keys[0] is obj.address)
        self.assertEqual(10, obj.value)
        obj = objs[2345]
        self.assertEqual("module", obj.type_str)
        self.assertEqual("mymod", obj.value)
        obj = objs[4567]
        # Known failure? We don't unescape properly, also, I'm surprised this
        # works. " should exit the " string, but \" seems to leave it. But the
        # '\' is also left verbatim because it is a raw string...
        self.assertEqual(r"Test \'whoami\'\u000a\"Your name\"", obj.value)

    def test_load_example(self):
        objs = loader.load(_example_dump, show_prog=False)

    def test_load_defaults_to_computing_and_collapsing(self):
        manager = loader.load(_instance_dump, show_prog=False, collapse=False)
        instance_obj = manager[1]
        self.assertEqual([2, 3], instance_obj.children)
        manager = loader.load(_instance_dump, show_prog=False)
        instance_obj = manager[1]
        self.assertEqual([4, 5, 6, 7, 9, 10, 11, 12, 3], instance_obj.children)

    def test_load_compressed(self):
        # unfortunately NamedTemporaryFile's cannot be re-opened on Windows
        fd, name = tempfile.mkstemp(prefix='meliae-')
        f = os.fdopen(fd, 'wb')
        try:
            content = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=f)
            for line in _example_dump:
                content.write(line + '\n')
            content.flush()
            content.close()
            del content
            f.close()
            objs = loader.load(name, show_prog=False).objs
            objs[1]
        finally:
            f.close()
            os.remove(name)

    def test_get_all(self):
        om = loader.load(_example_dump, show_prog=False)
        the_ints = om.get_all('int')
        self.assertEqual(2, len(the_ints))
        self.assertEqual([4, 5], sorted([i.address for i in the_ints]))

    def test_one(self):
        om = loader.load(_example_dump, show_prog=False)
        an_int = om[5]
        self.assertEqual(5, an_int.address)
        self.assertEqual('int', an_int.type_str)


class TestRemoveExpensiveReferences(tests.TestCase):

    def test_remove_expensive_references(self):
        lines = list(_example_dump)
        lines.pop(-1) # Remove the old module
        lines.append('{"address": 8, "type": "module", "size": 12'
                     ', "name": "mymod", "refs": [9]}')
        lines.append('{"address": 9, "type": "dict", "size": 124'
                     ', "refs": [10, 11]}')
        lines.append('{"address": 10, "type": "module", "size": 12'
                     ', "name": "mod2", "refs": [12]}')
        lines.append('{"address": 11, "type": "str", "size": 27'
                     ', "value": "boo", "refs": []}')
        lines.append('{"address": 12, "type": "dict", "size": 124'
                     ', "refs": []}')
        source = lambda:loader.iter_objs(lines)
        mymod_dict = list(source())[8]
        self.assertEqual([10, 11], mymod_dict.children)
        result = list(loader.remove_expensive_references(source))
        null_obj = result[0][1]
        self.assertEqual(0, null_obj.address)
        self.assertEqual('<ex-reference>', null_obj.type_str)
        self.assertEqual([11, 0], result[9][1].children)


class TestMemObj(tests.TestCase):

    def test_to_json(self):
        manager = loader.load(_example_dump, show_prog=False)
        objs = manager.objs.values()
        objs.sort(key=lambda x:x.address)
        expected = [
'{"address": 1, "type": "tuple", "size": 20, "refs": [2, 3]}',
'{"address": 2, "type": "dict", "size": 124, "refs": [4, 5, 6, 7]}',
'{"address": 3, "type": "list", "size": 44, "refs": [3, 4, 5]}',
'{"address": 4, "type": "int", "size": 12, "value": 2, "refs": []}',
'{"address": 5, "type": "int", "size": 12, "value": 1, "refs": []}',
'{"address": 6, "type": "str", "size": 29, "value": "a str", "refs": []}',
'{"address": 7, "type": "tuple", "size": 20, "refs": [4, 5]}',
'{"address": 8, "type": "module", "size": 60, "value": "mymod", "refs": [2]}',
        ]
        self.assertEqual(expected, [obj.to_json() for obj in objs])


class TestObjManager(tests.TestCase):

    def test_compute_parents(self):
        manager = loader.load(_example_dump, show_prog=False)
        manager.compute_parents()
        objs = manager.objs
        self.assertEqual((), objs[1].parents)
        self.assertEqual([1, 8], objs[2].parents)
        self.assertEqual([1, 3], objs[3].parents)
        self.assertEqual([2, 3, 7], objs[4].parents)
        self.assertEqual([2, 3, 7], objs[5].parents)
        self.assertEqual([2], objs[6].parents)
        self.assertEqual([2], objs[7].parents)
        self.assertEqual((), objs[8].parents)

    def test_compute_referrers(self):
        # Deprecated
        logged = []
        def log_warn(msg, klass, stacklevel=None):
            logged.append((msg, klass, stacklevel))
        old_func = warn.trap_warnings(log_warn)
        try:
            manager = loader.load(_example_dump, show_prog=False)
            manager.compute_referrers()
            self.assertEqual([('.compute_referrers is deprecated.'
                               ' Use .compute_parents instead.',
                               DeprecationWarning, 3),
                             ], logged)
            objs = manager.objs
        finally:
            warn.trap_warnings(old_func)
        self.assertEqual((), objs[1].parents)
        self.assertEqual([1, 8], objs[2].parents)
        self.assertEqual([1, 3], objs[3].parents)
        self.assertEqual([2, 3, 7], objs[4].parents)
        self.assertEqual([2, 3, 7], objs[5].parents)
        self.assertEqual([2], objs[6].parents)
        self.assertEqual([2], objs[7].parents)
        self.assertEqual((), objs[8].parents)

    def test_compute_total_size(self):
        manager = loader.load(_example_dump, show_prog=False)
        objs = manager.objs
        manager.compute_total_size(objs[1])
        self.assertEqual(261, objs[1].total_size)

    def test_compute_total_size_missing_ref(self):
        lines = list(_example_dump)
        # 999 isn't in the dump, not sure how we get these in real life, but
        # they exist. we should live with references that can't be resolved.
        lines[-1] = ('{"address": 8, "type": "tuple", "size": 16, "len": 1'
                     ', "refs": [999]}')
        manager = loader.load(lines, show_prog=False)
        obj = manager[8]
        manager.compute_total_size(obj)
        self.assertEqual(16, obj.total_size)

    def test_remove_expensive_references(self):
        lines = list(_example_dump)
        lines.pop(-1) # Remove the old module
        lines.append('{"address": 8, "type": "module", "size": 12'
                     ', "name": "mymod", "refs": [9]}')
        lines.append('{"address": 9, "type": "dict", "size": 124'
                     ', "refs": [10, 11]}')
        lines.append('{"address": 10, "type": "module", "size": 12'
                     ', "name": "mod2", "refs": [12]}')
        lines.append('{"address": 11, "type": "str", "size": 27'
                     ', "value": "boo", "refs": []}')
        lines.append('{"address": 12, "type": "dict", "size": 124'
                     ', "refs": []}')
        manager = loader.load(lines, show_prog=False, collapse=False)
        mymod_dict = manager.objs[9]
        self.assertEqual([10, 11], mymod_dict.children)
        manager.remove_expensive_references()
        self.assertTrue(0 in manager.objs)
        null_obj = manager.objs[0]
        self.assertEqual(0, null_obj.address)
        self.assertEqual('<ex-reference>', null_obj.type_str)
        self.assertEqual([11, 0], mymod_dict.children)

    def test_collapse_instance_dicts(self):
        manager = loader.load(_instance_dump, show_prog=False, collapse=False)
        # This should collapse all of the references from the instance's dict
        # @2 into the instance @1
        instance = manager.objs[1]
        self.assertEqual(32, instance.size)
        self.assertEqual([2, 3], instance.children)
        inst_dict = manager.objs[2]
        self.assertEqual(140, inst_dict.size)
        self.assertEqual([4, 5, 6, 7, 9, 10, 11, 12], inst_dict.children)
        mod = manager.objs[14]
        self.assertEqual([15], mod.children)
        mod_dict = manager.objs[15]
        self.assertEqual([5, 6, 9, 6], mod_dict.children)
        manager.compute_parents()
        tpl = manager.objs[12]
        self.assertEqual([2], tpl.parents)
        self.assertEqual([1], inst_dict.parents)
        self.assertEqual([14], mod_dict.parents)
        manager.collapse_instance_dicts()
        # The instance dict has been removed
        self.assertEqual([4, 5, 6, 7, 9, 10, 11, 12, 3], instance.children)
        self.assertEqual(172, instance.size)
        self.assertFalse(2 in manager.objs)
        self.assertEqual([1], tpl.parents)
        self.assertEqual([5, 6, 9, 6], mod.children)
        self.assertFalse(15 in manager.objs)

    def test_collapse_old_instance_dicts(self):
        manager = loader.load(_old_instance_dump, show_prog=False,
                              collapse=False)
        instance = manager.objs[1]
        self.assertEqual('instance', instance.type_str)
        self.assertEqual(36, instance.size)
        self.assertEqual([2, 3], instance.children)
        inst_dict = manager[3]
        self.assertEqual(140, inst_dict.size)
        self.assertEqual([4, 5, 6, 7], inst_dict.children)
        manager.compute_parents()
        manager.collapse_instance_dicts()
        # The instance dict has been removed, and its references moved into the
        # instance, further, the type has been updated from generic 'instance'
        # to being 'OldStyle'.
        self.assertFalse(3 in manager.objs)
        self.assertEqual(176, instance.size)
        self.assertEqual([4, 5, 6, 7, 2], instance.children)
        self.assertEqual('OldStyle', instance.type_str)

    def test_expand_refs_as_dict(self):
        # TODO: This test fails if simplejson is not installed, because the
        #       regex extractor does not cast to integers (they stay as
        #       strings). We could fix the test, or fix the extractor.
        manager = loader.load(_instance_dump, show_prog=False, collapse=False)
        as_dict = manager.refs_as_dict(manager[15])
        self.assertEqual({1: 'c', 'b': 'c'}, as_dict)
        manager.compute_parents()
        manager.collapse_instance_dicts()
        self.assertEqual({1: 'c', 'b': 'c'}, manager.refs_as_dict(manager[14]))
        self.assertEqual({'a': 1, 'c': manager[7], 'b': 'string',
                          'd': manager[12]}, manager.refs_as_dict(manager[1]))

    def test_expand_refs_as_list(self):
        # TODO: This test fails if simplejson is not installed, because the
        #       regex extractor does not cast to integers (they stay as
        #       strings). We could fix the test, or fix the extractor.
        manager = loader.load(_instance_dump, show_prog=False)
        self.assertEqual([2], manager.refs_as_list(manager[12]))

    def test_guess_intern_dict(self):
        manager = loader.load(_intern_dict_dump, show_prog=False)
        obj = manager.guess_intern_dict()
        self.assertEqual(8, obj.address)

    def test_summarize_refs(self):
        manager = loader.load(_example_dump, show_prog=False)
        summary = manager.summarize(manager[2])
        # Note that the dict itself is not excluded from the summary
        self.assertEqual(['dict', 'int', 'str', 'tuple'],
                         sorted(summary.type_summaries.keys()))
        self.assertEqual(197, summary.total_size)

    def test_summarize_excluding(self):
        manager = loader.load(_example_dump, show_prog=False)
        summary = manager.summarize(manager[2], excluding=[4, 5])
        # No ints when they are explicitly filtered
        self.assertEqual(['dict', 'str', 'tuple'],
                         sorted(summary.type_summaries.keys()))
        self.assertEqual(173, summary.total_size)
