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

    def test__len__(self):
        moc = _loader.MemObjectCollection()
        self.assertEqual(0, len(moc))
        moc.add(0, 'foo', 100)
        self.assertEqual(1, len(moc))
        moc.add(1024, 'foo', 100)
        self.assertEqual(2, len(moc))
        del moc[0]
        self.assertEqual(1, len(moc))
        del moc[1024]
        self.assertEqual(0, len(moc))

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

    def test_get(self):
        moc = _loader.MemObjectCollection()
        self.assertEqual(None, moc.get(0, None))
        moc.add(0, 'foo', 100)
        self.assertEqual(100, moc.get(0, None).size)

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

    def test_itervalues(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'bar', 100)
        moc.add(1024, 'baz', 102)
        moc.add(512, 'bing', 103)
        self.assertEqual([0, 1024, 512], [x.address for x in moc.itervalues()])
        del moc[0]
        self.assertEqual([1024, 512], [x.address for x in moc.itervalues()])

    def test_items(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'bar', 100)
        moc.add(1024, 'baz', 102)
        moc.add(512, 'bing', 103)
        items = moc.items()
        self.assertTrue(isinstance(items, list))
        self.assertEqual([(0, 0), (1024, 1024), (512, 512)],
                         [(k, v.address) for k,v in items])
        del moc[0]
        self.assertEqual([(1024, 1024), (512, 512)],
                         [(k, v.address) for k,v in moc.items()])

    def test_iteritems(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'bar', 100)
        moc.add(1024, 'baz', 102)
        moc.add(512, 'bing', 103)
        self.assertEqual([(0, 0), (1024, 1024), (512, 512)],
                         [(k, v.address) for k,v in moc.iteritems()])
        del moc[0]
        self.assertEqual([(1024, 1024), (512, 512)],
                         [(k, v.address) for k,v in moc.iteritems()])

    def test_keys(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'bar', 100)
        moc.add(1024, 'baz', 102)
        moc.add(512, 'bing', 103)
        keys = moc.keys()
        self.assertTrue(isinstance(keys, list))
        self.assertEqual([0, 1024, 512], keys)
        del moc[0]
        self.assertEqual([1024, 512], moc.keys())

    def test__iter__(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'bar', 100)
        moc.add(1024, 'baz', 102)
        moc.add(512, 'bing', 103)
        self.assertEqual([0, 1024, 512], list(moc))
        self.assertEqual([0, 1024, 512], list(moc.iterkeys()))
        del moc[0]
        self.assertEqual([1024, 512], list(moc))
        self.assertEqual([1024, 512], list(moc.iterkeys()))


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

    def test_deleted_proxy(self):
        mop = self.moc[0]
        del self.moc[0]
        self.assertFalse(mop.is_valid())
        self.assertRaises(RuntimeError, lambda: mop.type_str)
        self.assertRaises(RuntimeError, lambda: mop.size)
        self.assertRaises(RuntimeError, len, mop)

    def test_value(self):
        mop = self.moc.add(1234, 'type', 256, value='testval')
        self.assertEqual('testval', mop.value)
        mop.value = None
        self.assertEqual(None, mop.value)
        mop.value = 'a str'
        self.assertEqual('a str', mop.value)
        mop.value = 'a str'
        self.assertEqual('a str', mop.value)

    def test_name(self):
        mop = self.moc.add(1234, 'type', 256, name='the name')
        self.assertEqual('the name', mop.name)
        # TODO: We may remove name as a separate attribute from value, but for
        #       now, 'name' is not settable
        def set(value):
            mop.name = value
        self.assertRaises(AttributeError, set, 'test')

    def test__intern_from_cache(self):
        cache = {}
        addr = 1234567
        mop = self.moc.add(addr, 'my ' + ' type', 256)
        mop._intern_from_cache(cache)
        self.assertTrue(addr in cache)
        # TODO: ref_list and referrers
        self.assertTrue(mop.address is addr)
        self.assertTrue(cache[addr] is addr)
        t = cache['my  type']
        self.assertTrue(mop.type_str is t)
        del self.moc[addr]
        mop = self.moc.add(1234566+1, 'my ' + ' ty' + 'pe', 256)
        self.assertFalse(mop.address is addr)
        self.assertFalse(mop.type_str is t)
        mop._intern_from_cache(cache)
        self.assertTrue(mop.address is addr)
        self.assertTrue(mop.type_str is t)

    def test_ref_list(self):
        mop = self.moc.add(1234567, 'type', 256, ref_list=[1, 2, 3])
        self.assertEqual(3, len(mop))
        self.assertEqual([1, 2, 3], mop.ref_list)
        mop.ref_list = [87654321, 23456]
        self.assertEqual([87654321, 23456], mop.ref_list)
        self.assertEqual(2, len(mop))

    def test__getitem__(self):
        mop = self.moc.add(1234567, 'type', 256, ref_list=[0, 255])
        self.assertEqual(2, len(mop))
        self.assertEqual(2, len(list(mop)))
        mop0 = mop[0]
        mop255 = mop[1]
        self.assertEqual([mop0, mop255], list(mop))
        self.assertEqual(0, mop0.address)
        self.assertEqual('foo', mop0.type_str)
        self.assertEqual(255, mop255.address)
        self.assertEqual('baz', mop255.type_str)

    def test_total_size(self):
        mop = self.moc[0]
        self.assertEqual(0, mop.total_size)
        mop.total_size = 10245678
        self.assertEqual(10245678, mop.total_size)
        mop.total_size = (2**31+1)
        self.assertEqual(2**31+1, mop.total_size)

    def test_referrers(self):
        mop = self.moc.add(1234567, 'type', 256, ref_list=[0, 255])
        mop0 = self.moc[0]
        self.assertEqual((), mop0.referrers)
        mop255 = self.moc[255]
        self.assertEqual((), mop255.referrers)
        mop0.referrers = [1234567]
        self.assertEqual([1234567], mop0.referrers)
        mop255.referrers = [1234567]
        self.assertEqual([1234567], mop255.referrers)
