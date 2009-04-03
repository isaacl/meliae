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


_example_dump = [
'{"address": 505264624, "type": "NoneType", "size": 8, "refs": []}',
'{"address": 505179844, "type": "bool", "size": 12, "refs": []}',
'{"address": 505179832, "type": "bool", "size": 12, "refs": []}',
'{"address": 23038136, "type": "int", "size": 12, "value": -5, "refs": []}',
'{"address": 23038124, "type": "int", "size": 12, "value": -4, "refs": []}',
'{"address": 23038112, "type": "int", "size": 12, "value": -3, "refs": []}',
'{"address": 23038100, "type": "int", "size": 12, "value": -2, "refs": []}',
'{"address": 23038088, "type": "int", "size": 12, "value": -1, "refs": []}',
'{"address": 23038076, "type": "int", "size": 12, "value": 0, "refs": []}',
'{"address": 23038064, "type": "int", "size": 12, "value": 1, "refs": []}',
'{"address": 23038052, "type": "int", "size": 12, "value": 2, "refs": []}',
'{"address": 23038040, "type": "int", "size": 12, "value": 3, "refs": []}',
'{"address": 23038028, "type": "int", "size": 12, "value": 4, "refs": []}',
'{"address": 23038016, "type": "int", "size": 12, "value": 5, "refs": []}',
'{"address": 23038004, "type": "int", "size": 12, "value": 6, "refs": []}',
'{"address": 23037992, "type": "int", "size": 12, "value": 7, "refs": []}',
'{"address": 23037980, "type": "int", "size": 12, "value": 8, "refs": []}',
'{"address": 23037968, "type": "int", "size": 12, "value": 9, "refs": []}',
'{"address": 23037956, "type": "int", "size": 12, "value": 10, "refs": []}',
'{"address": 1234, "type": "tuple", "size": 20, "refs": [505264624, 23038064]}',
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
        self.assertEqual((), objs[1234]._referrers)
        self.assertEqual((1234,), objs[505264624]._referrers)
        self.assertEqual((1234,), objs[23038064]._referrers)
