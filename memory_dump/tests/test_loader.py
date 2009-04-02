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
    loader,
    tests,
    )


class TestMemObject(tests.TestCase):

    def test_from_json_dict(self):
        mem = loader.MemObject.from_json_dict(
            dict(address=1024, type=u'str', size=10, refs=[], len=4,
                value=u'abcd'))
        self.assertEqual(1024, mem.address)
        self.assertEqual('str', mem.type_str)
        self.assertEqual(10, mem.size)
        self.assertEqual([], mem.ref_list)
        self.assertEqual(4, mem.length)
        self.assertEqual('abcd', mem.value)
        self.assertEqual(None, mem.name)
        self.assertEqual(None, mem.total_size)

    def test__fill_total_size(self):
        objs = {
            1: loader.MemObject(1, 'type', 10, []),
            2: loader.MemObject(2, 'type', 20, [1]),
        }
        loader._fill_total_size(objs)
        self.assertEqual(10, objs[1].total_size)
        self.assertEqual(30, objs[2].total_size)

    def test__fill_total_size_cycle(self):
        objs = {
            1: loader.MemObject(1, 'type', 10, [2]),
            2: loader.MemObject(2, 'type', 20, [1]),
        }
        loader._fill_total_size(objs)
        # self.assertEqual(30, objs[1].total_size)
        # self.assertEqual(30, objs[2].total_size)

    def test__fill_total_size_wide_cycle(self):
        objs = {
            1: loader.MemObject(1, 'type', 10, [5]),
            2: loader.MemObject(2, 'type', 20, [1]),
            3: loader.MemObject(3, 'type', 30, [2]),
            4: loader.MemObject(4, 'type', 40, [3]),
            5: loader.MemObject(5, 'type', 50, [4]),
            6: loader.MemObject(6, 'type', 5, [1]),
        }
        loader._fill_total_size(objs)
        # self.assertEqual(150, objs[1].total_size)
        # self.assertEqual(150, objs[2].total_size)
        self.assertEqual(155, objs[6].total_size)
