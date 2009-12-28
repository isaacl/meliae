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

    def test__getitem__(self):
        mem = _loader.MemObject(1234, 'tuple', 12, [])
        def get(offset):
            return mem[offset]
        self.assertRaises(IndexError, get, 0)
        self.assertRaises(IndexError, get, 1)
        self.assertRaises(IndexError, get, -1)
        mem = _loader.MemObject(1234, 'tuple', 20, [4567, 8901])
        self.assertEqual(4567, mem[0])
        self.assertEqual(8901, mem[1])

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


class TestMemObjectCollection(tests.TestCase):
    
    def test__init__(self):
        moc = _loader.MemObjectCollection()
        self.assertEqual(0, moc._active)
        self.assertEqual(0, moc._filled)
        self.assertEqual(1023, moc._table_mask)

    def test__lookup_direct(self):
        moc = _loader.MemObjectCollection()
        self.assertEqual(1023, moc._table_mask)
        self.assertEqual(0, moc._test_lookup(0))
        self.assertEqual(0, moc._test_lookup(1024))
        self.assertEqual(255, moc._test_lookup(255))
        self.assertEqual(933, moc._test_lookup(933))
        self.assertEqual(933, moc._test_lookup(933+1024))
        self.assertEqual(933, moc._test_lookup(933L+1024L))
        self.assertEqual(933, moc._test_lookup(933L+2**32-1))

    def test__lookup_collide(self):
        moc = _loader.MemObjectCollection()
        self.assertEqual(1023, moc._table_mask)
        self.assertEqual(0, moc._test_lookup(0))
        self.assertEqual(0, moc._test_lookup(1024))
        moc.add(0, 'foo', 100)
        self.assertEqual(0, moc._test_lookup(0))
        self.assertEqual(1, moc._test_lookup(1024))
        moc.add(1024, 'bar', 200)
        self.assertEqual(0, moc._test_lookup(0))
        self.assertEqual(1, moc._test_lookup(1024))

    def test__contains__(self):
        moc = _loader.MemObjectCollection()
        self.assertEqual(0, moc._test_lookup(0))
        self.assertEqual(0, moc._test_lookup(1024))
        self.assertFalse(0 in moc)
        self.assertFalse(1024 in moc)
        moc.add(0, 'foo', 100)
        self.assertTrue(0 in moc)
        self.assertFalse(1024 in moc)
        moc.add(1024, 'bar', 200)
        self.assertTrue(0 in moc)
        self.assertTrue(1024 in moc)

    def test__getitem__(self):
        moc = _loader.MemObjectCollection()
        def get(offset):
            return moc[offset]
        self.assertRaises(KeyError, get, 0)
        self.assertRaises(KeyError, get, 1024)
        moc.add(0, 'foo', 100)
        mop = moc[0]
        self.assertTrue(isinstance(mop, _loader._MemObjectProxy))
        self.assertEqual('foo', mop.type_str)
        self.assertEqual(100, mop.size)
        self.assertRaises(KeyError, get, 1024)
        self.assertTrue(mop is moc[mop])

    def test__delitem__(self):
        moc = _loader.MemObjectCollection()
        def get(offset):
            return moc[offset]
        def delete(offset):
            del moc[offset]
        self.assertRaises(KeyError, delete, 0)
        self.assertRaises(KeyError, delete, 1024)
        moc.add(0, 'foo', 100)
        self.assertTrue(0 in moc)
        self.assertFalse(1024 in moc)
        self.assertRaises(KeyError, delete, 1024)
        moc.add(1024, 'bar', 200)
        del moc[0]
        self.assertFalse(0 in moc)
        self.assertRaises(KeyError, get, 0)
        mop = moc[1024]
        del moc[mop]
        self.assertRaises(KeyError, get, 1024)

    def test_add_until_resize(self):
        moc = _loader.MemObjectCollection()
        for i in xrange(1025):
            moc.add(i, 'foo', 100+i)
        self.assertEqual(1025, moc._filled)
        self.assertEqual(1025, moc._active)
        self.assertEqual(2047, moc._table_mask)
        mop = moc[1024]
        self.assertEqual(1024, mop.address)
        self.assertEqual(1124, mop.size)


class Test_MemObjectProxy(tests.TestCase):

    def setUp(self):
        super(Test_MemObjectProxy, self).setUp()
        self.moc = _loader.MemObjectCollection()
        self.moc.add(1024, 'bar', 200)
        self.moc.add(0, 'foo', 100)
        self.moc.add(255, 'baz', 300)
        del self.moc[1024]

    def test_basic_proxy(self):
        mop = self.moc[0]
        self.assertEqual(0, mop.address)
        self.assertEqual('foo', mop.type_str)
        self.assertEqual(100, mop.size)
        mop.size = 1024
        self.assertEqual(1024, mop.size)
        self.assertEqual(1024, self.moc[0].size)
        self.assertEqual(0, len(mop))
