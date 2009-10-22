# Copyright (C) 2009 Canonical Ltd
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
'{"address": 6, "type": "str", "size": 29, "name": "bah", "len": 5, "value": "a str"'
 ', "refs": []}',
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
        if test_dict_id > sys.maxint:
            # We wrapped around to the negative value, note, this needs to be
            # re-evaluated for 64-bit versions of python
            test_dict_id = int(test_dict_id - 2 * (sys.maxint + 1))
        self.assertTrue(test_dict_id in manager.objs)

    def test_load_one(self):
        objs = loader.load([
            '{"address": 1234, "type": "int", "size": 12, "value": 10'
            ', "refs": []}'], show_prog=False).objs
        keys = objs.keys()
        self.assertEqual([1234], keys)
        obj = objs[1234]
        self.assertTrue(isinstance(obj, _loader.MemObject))
        # The address should be exactly the same python object as the key in
        # the objs dictionary.
        self.assertTrue(keys[0] is obj.address)

    def test_load_example(self):
        objs = loader.load(_example_dump, show_prog=False)

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
        self.assertEqual([10, 11], mymod_dict.ref_list)
        result = list(loader.remove_expensive_references(source))
        null_obj = result[0][1]
        self.assertEqual(0, null_obj.address)
        self.assertEqual('<ex-reference>', null_obj.type_str)
        self.assertEqual([11, 0], result[9][1].ref_list)


class TestMemObj(tests.TestCase):

    def test_to_json(self):
        objs = list(loader.iter_objs(_example_dump))
        objs.sort(key=lambda x:x.address)
        expected = sorted(_example_dump)
        self.assertEqual(expected, [obj.to_json() for obj in objs])


class TestObjManager(tests.TestCase):

    def test_compute_referrers(self):
        manager = loader.load(_example_dump, show_prog=False)
        manager.compute_referrers()
        objs = manager.objs
        self.assertEqual((), objs[1].referrers)
        self.assertEqual([1], objs[2].referrers)
        self.assertEqual([1, 3], objs[3].referrers)
        self.assertEqual([2, 3, 7], objs[4].referrers)
        self.assertEqual([2, 3, 7], objs[5].referrers)
        self.assertEqual([2], objs[6].referrers)
        self.assertEqual([2], objs[7].referrers)

    def test_compute_total_size(self):
        manager = loader.load(_example_dump, show_prog=False)
        manager.compute_total_size()
        objs = manager.objs
        self.assertEqual(261, objs[1].total_size)
        self.assertEqual(197, objs[2].total_size)
        self.assertEqual(68, objs[3].total_size)
        self.assertEqual(12, objs[4].total_size)
        self.assertEqual(12, objs[5].total_size)
        self.assertEqual(29, objs[6].total_size)
        self.assertEqual(44, objs[7].total_size)

    def test_compute_total_size_missing_ref(self):
        lines = list(_example_dump)
        # 999 isn't in the dump, not sure how we get these in real life, but
        # they exist
        lines.append('{"address": 8, "type": "tuple", "size": 16, "len": 1'
                     ', "refs": [999]}')
        manager = loader.load(lines, show_prog=False)
        manager.compute_total_size()

    def test_remove_expensive_references(self):
        lines = list(_example_dump)
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
        manager = loader.load(lines, show_prog=False)
        mymod_dict = manager.objs[9]
        self.assertEqual([10, 11], mymod_dict.ref_list)
        manager.remove_expensive_references()
        self.assertTrue(0 in manager.objs)
        null_obj = manager.objs[0]
        self.assertEqual(0, null_obj.address)
        self.assertEqual('<ex-reference>', null_obj.type_str)
        self.assertEqual([11, 0], mymod_dict.ref_list)

    def test_collapse_instance_dicts(self):
        manager = loader.load(_instance_dump, show_prog=False)
        # This should collapse all of the references from the instance's dict
        # @2 into the instance @1
        instance = manager.objs[1]
        self.assertEqual(32, instance.size)
        self.assertEqual([2, 3], instance.ref_list)
        inst_dict = manager.objs[2]
        self.assertEqual(140, inst_dict.size)
        self.assertEqual([4, 5, 6, 7, 9, 10, 11, 12], inst_dict.ref_list)
        mod = manager.objs[14]
        self.assertEqual([15], mod.ref_list)
        mod_dict = manager.objs[15]
        self.assertEqual([5, 6, 9, 6], mod_dict.ref_list)
        manager.compute_referrers()
        tpl = manager.objs[12]
        self.assertEqual([2], tpl.referrers)
        self.assertEqual([1], inst_dict.referrers)
        self.assertEqual([14], mod_dict.referrers)
        manager.collapse_instance_dicts()
        # The instance dict has been removed
        self.assertEqual([4, 5, 6, 7, 9, 10, 11, 12, 3], instance.ref_list)
        self.assertEqual(172, instance.size)
        self.assertFalse(2 in manager.objs)
        self.assertEqual([1], tpl.referrers)
        self.assertEqual([5, 6, 9, 6], mod.ref_list)
        self.assertFalse(15 in manager.objs)

    def test_expand_refs_as_dict(self):
        manager = loader.load(_instance_dump, show_prog=False)
        as_dict = manager.refs_as_dict(manager[15])
        self.assertEqual({1: 'c', 'b': 'c'}, as_dict)
        manager.compute_referrers()
        manager.collapse_instance_dicts()
        self.assertEqual({1: 'c', 'b': 'c'}, manager.refs_as_dict(manager[14]))
        self.assertEqual({'a': 1, 'c': manager[7], 'b': 'string',
                          'd': manager[12]}, manager.refs_as_dict(manager[1]))

    def test_expand_refs_as_list(self):
        manager = loader.load(_instance_dump, show_prog=False)
        self.assertEqual([2], manager.refs_as_list(manager[12]))
