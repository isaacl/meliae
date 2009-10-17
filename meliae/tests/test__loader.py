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

"""Pyrex extension for tracking loaded objects"""

from meliae import (
    _loader,
    tests,
    )


class TestMemObject(tests.TestCase):

    def test_test_simple_attributes(self):
        mem = _loader.MemObject(1234, 'int', 12, [])
        self.assertEqual(1234, mem.address)
        # Make sure we don't cast into PyLong
        self.assertTrue(isinstance(mem.address, int))
        self.assertEqual('int', mem.type_str)
        self.assertEqual(12, mem.size)
        self.assertTrue(isinstance(mem.size, int))
        self.assertEqual((), mem.ref_list)
        self.assertEqual(0, mem.total_size)

    def test_ref_list(self):
        mem = _loader.MemObject(1234, 'tuple', 20, [4567, 8901])
        self.assertEqual([4567, 8901], mem.ref_list)
        mem.ref_list = [999, 4567, 0]
        self.assertEqual([999, 4567, 0], mem.ref_list)
        self.assertEqual(3, mem.num_refs)

    def test_num_refs(self):
        mem = _loader.MemObject(1234, 'tuple', 20, [4567, 8901])
        self.assertEqual(2, mem.num_refs)
        mem = _loader.MemObject(1234, 'tuple', 12, [])
        self.assertEqual(0, mem.num_refs)

    def test_num_referrers(self):
        mem = _loader.MemObject(1234, 'tuple', 20, [4567, 8901])
        mem.referrers = ()
        self.assertEqual(0, mem.num_referrers)
        self.assertEqual((), mem.referrers)
        mem.referrers = [1, 2, 3]
        self.assertEqual(3, mem.num_referrers)
        self.assertEqual([1, 2, 3], mem.referrers)

    def test_total_size(self):
        mem = _loader.MemObject(1234, 'tuple', 20, [4567, 8901])
        self.assertEqual(0, mem.total_size)
        mem.total_size = 100
        self.assertEqual(100, mem.total_size)

    def test__repr__(self):
        mem = _loader.MemObject(1234, 'str', 24, [])
        self.assertEqual('MemObject(1234, str, 24 bytes'
                         ', 0 refs)', repr(mem))
        mem = _loader.MemObject(1234, 'tuple', 12, [4567, 8900])
        self.assertEqual('MemObject(1234, tuple, 12 bytes'
                         ', 2 refs [4567, 8900])', repr(mem))
        mem = _loader.MemObject(1234, 'module', 12, [4567, 8900],
                                name='named')
        self.assertEqual('MemObject(1234, module, named, 12 bytes'
                         ', 2 refs [4567, 8900])', repr(mem))
        mem = _loader.MemObject(1234, 'module', 12, range(20))
        self.assertEqual('MemObject(1234, module, 12 bytes'
                         ', 20 refs [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ...])',
                         repr(mem))
        mem = _loader.MemObject(1234, 'foo', 12, [10])
        mem.referrers = [20, 30]
        self.assertEqual('MemObject(1234, foo, 12 bytes'
                         ', 1 refs [10], 2 referrers [20, 30])',
                         repr(mem))
        mem = _loader.MemObject(1234, 'str', 24, [])
        mem.value = 'teststr'
        self.assertEqual('MemObject(1234, str, 24 bytes'
                         ', 0 refs, \'teststr\')', repr(mem))
        mem.value = 'averylongstringwithmorestuff'
        self.assertEqual('MemObject(1234, str, 24 bytes'
                         ', 0 refs, \'averylongstringwi...)', repr(mem))
        mem = _loader.MemObject(1234, 'int', 12, [])
        mem.value = 12345
        self.assertEqual('MemObject(1234, int, 12 bytes'
                         ', 0 refs, 12345)', repr(mem))
        mem.total_size = 12
        self.assertEqual('MemObject(1234, int, 12 bytes'
                         ', 0 refs, 12345, 12.0B)', repr(mem))
        mem.total_size = 1024
        self.assertEqual('MemObject(1234, int, 12 bytes'
                         ', 0 refs, 12345, 1.0KiB)', repr(mem))
        mem.total_size = int(1024*1024*10.5)
        self.assertEqual('MemObject(1234, int, 12 bytes'
                         ', 0 refs, 12345, 10.5MiB)', repr(mem))
