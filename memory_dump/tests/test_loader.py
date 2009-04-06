# Copyright (C) 2009 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Read back in a dump file and process it"""

from memory_dump import (
    _loader,
    loader,
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
'{"address": 2, "type": "dict", "size": 124, "len": 2, "refs": [5, 4, 6, 7]}',
'{"address": 7, "type": "tuple", "size": 20, "len": 2, "refs": [4, 5]}',
'{"address": 6, "type": "str", "size": 29, "len": 5, "value": "a str"'
 ', "refs": []}',
]

class TestLoad(tests.TestCase):

    def test_load_one(self):
        objs = loader.load([
            '{"address": 1234, "type": "int", "size": 12, "value": 10'
            ', "refs": []}'], show_prog=False).objs
        self.assertEqual([1234], objs.keys())
        obj = objs[1234]
        self.assertTrue(isinstance(obj, _loader.MemObject))

    def test_load_example(self):
        objs = loader.load(_example_dump, show_prog=False)


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
