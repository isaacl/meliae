# Copyright (C) 2009, 2010, 2011 Canonical Ltd
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
    _scanner,
    warn,
    tests,
    )

# Empty table size is 1024 pointers
# 1: PyType*
# 2: refcnt
# 3: vtable*
# 4: _table*
# 3 4-byte int attributes
# Note that on 64-bit platforms, alignment issues mean we will still
# round to a multiple-of-8 bytes.
_memobj_extra_size = 3*4
if (_memobj_extra_size % _scanner._word_size) != 0:
    _memobj_extra_size += (_scanner._word_size
                           - (_memobj_extra_size % _scanner._word_size))

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

    def test_itervalues_to_tip(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'bar', 100)
        moc.add(1024, 'baz', 102)
        moc.add(512, 'bing', 104)
        self.assertEqual([0, 1024, 512],
                         [x.address for x in moc.itervalues()])
        del moc[0]
        self.assertEqual([1024, 512],
                         [x.address for x in moc.itervalues()])
        moc.add(1023, 'booze', 103)
        self.assertEqual([1024, 512, 1023],
                         [x.address for x in moc.itervalues()])
        del moc[1023]
        self.assertEqual([1024, 512],
                         [x.address for x in moc.itervalues()])

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

    def assertSizeOf(self, num_words, obj, extra_size=0, has_gc=True):
        expected_size = extra_size + num_words * _scanner._word_size
        if has_gc:
            expected_size += _scanner._gc_head_size
        self.assertEqual(expected_size, _scanner.size_of(obj))

    def test__sizeof__base(self):
        moc = _loader.MemObjectCollection()
        # Empty table size is 1024 pointers
        # 1: PyType*
        # 2: refcnt
        # 3: vtable*
        # 4: _table*
        # 3 4-byte int attributes
        # Note that on 64-bit platforms, alignment issues mean we will still
        # round to a multiple-of-8 bytes.
        self.assertSizeOf(4+1024, moc, extra_size=_memobj_extra_size,
                          has_gc=False)

    def test__sizeof__one_item(self):
        moc = _loader.MemObjectCollection()
        # We also track the size of the referenced _MemObject entries
        # Which is:
        # 1: PyObject *address
        # 2: PyObject *type_str
        # 3: long size
        # 4: *child_list
        # 5: *value
        # 6: *parent_list
        # 7: ulong total_size
        # 8: *proxy
        moc.add(0, 'foo', 100)
        self.assertSizeOf(4+1024+8, moc, extra_size=_memobj_extra_size,
                          has_gc=False)

    def test__sizeof__with_reflists(self):
        moc = _loader.MemObjectCollection()
        # We should assign the memory for ref-lists to the container. A
        # ref-list allocates the number of entries + 1
        # Each _memobject also takes up
        moc.add(0, 'foo', 100, children=[1234], parent_list=[3456, 7890])
        self.assertSizeOf(4+1024+8+2+3, moc, extra_size=_memobj_extra_size,
                          has_gc=False)

    def test__sizeof__with_dummy(self):
        moc = _loader.MemObjectCollection()
        moc.add(0, 'foo', 100, children=[1234], parent_list=[3456, 7890])
        moc.add(1, 'foo', 100, children=[1234], parent_list=[3456, 7890])
        del moc[1]
        self.assertSizeOf(4+1024+8+2+3, moc, extra_size=_memobj_extra_size,
                          has_gc=False)

    def test_traverse_empty(self):
        # With nothing present, we return no referents
        moc = _loader.MemObjectCollection()
        self.assertEqual([], _scanner.get_referents(moc))

    def test_traverse_simple_item(self):
        moc = _loader.MemObjectCollection()
        moc.add(1234, 'foo', 100)
        self.assertEqual([1234, 'foo', None], _scanner.get_referents(moc))

    def test_traverse_multiple_and_parents_and_children(self):
        moc = _loader.MemObjectCollection()
        moc.add(1, 'foo', 100)
        moc.add(2, 'bar', 200, children=[8, 9], parent_list=[10, 11],
                value='test val')
        self.assertEqual([1, 'foo', None, 2, 'bar', 'test val', 8, 9, 10, 11],
                         _scanner.get_referents(moc))


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
        self.assertEqual('foo', mop.type_str)
        self.assertEqual(100, mop.size)
        self.assertEqual(0, len(mop))

    def test_value(self):
        mop = self.moc.add(1234, 'type', 256, value='testval')
        self.assertEqual('testval', mop.value)
        mop.value = None
        self.assertEqual(None, mop.value)
        mop.value = 'a str'
        self.assertEqual('a str', mop.value)
        mop.value = 'a str'
        self.assertEqual('a str', mop.value)

    def test_type_str(self):
        mop = self.moc.add(1234, 'type', 256, value='testval')
        self.assertEqual('type', mop.type_str)
        mop.type_str = 'difftype'
        self.assertEqual('difftype', mop.type_str)

    def test_name(self):
        mop = self.moc.add(1234, 'type', 256, name='the name')
        # 'name' entries get mapped as value
        self.assertEqual('the name', mop.value)

    def test__intern_from_cache(self):
        cache = {}
        addr = 1234567
        mop = self.moc.add(addr, 'my ' + ' type', 256)
        mop._intern_from_cache(cache)
        self.assertTrue(addr in cache)
        self.assertTrue(mop.address is addr)
        self.assertTrue(cache[addr] is addr)
        t = cache['my  type']
        self.assertTrue(mop.type_str is t)
        del self.moc[addr]
        mop = self.moc.add(1234566+1, 'my ' + ' ty' + 'pe', 256)
        addr876543 = 876543
        cache[addr876543] = addr876543
        addr654321 = 654321
        cache[addr654321] = addr654321
        mop.children = [876542+1, 654320+1]
        mop.parents = [876542+1, 654320+1]
        self.assertFalse(mop.address is addr)
        self.assertFalse(mop.type_str is t)
        rl = mop.children
        self.assertFalse(rl[0] is addr876543)
        self.assertFalse(rl[1] is addr654321)
        rfrs = mop.parents
        self.assertFalse(rl[0] is addr876543)
        self.assertFalse(rl[1] is addr654321)
        mop._intern_from_cache(cache)
        self.assertTrue(mop.address is addr)
        self.assertTrue(mop.type_str is t)
        rl = mop.children
        self.assertTrue(rl[0] is addr876543)
        self.assertTrue(rl[1] is addr654321)
        rfrs = mop.parents
        self.assertTrue(rfrs[0] is addr876543)
        self.assertTrue(rfrs[1] is addr654321)

    def test_children(self):
        mop = self.moc.add(1234567, 'type', 256, children=[1, 2, 3])
        self.assertEqual(3, len(mop))
        self.assertEqual([1, 2, 3], mop.children)
        mop.children = [87654321, 23456]
        self.assertEqual([87654321, 23456], mop.children)
        self.assertEqual(2, len(mop))

    def test_c(self):
        mop = self.moc.add(1234567, 'type', 256, children=[0, 255])
        mop0 = self.moc[0]
        self.assertEqual([], mop0.c)
        c = mop.c
        self.assertEqual(2, len(c))
        self.assertEqual(0, c[0].address)
        self.assertEqual(255, c[1].address)

    def test_ref_list(self):
        # Deprecated
        logged = []
        def log_warn(msg, klass, stacklevel=None):
            logged.append((msg, klass, stacklevel))
        old_func = warn.trap_warnings(log_warn)
        try:
            mop = self.moc.add(1234567, 'type', 256, children=[1, 2, 3])
            self.assertEqual(3, len(mop))
            self.assertEqual(3, mop.num_refs)
            self.assertEqual([('Attribute .num_refs deprecated.'
                               ' Use len() instead.', DeprecationWarning, 3),
                             ], logged)
            del logged[:]
            self.assertEqual([1, 2, 3], mop.ref_list)
            self.assertEqual([('Attribute .ref_list deprecated.'
                               ' Use .children instead.',
                               DeprecationWarning, 3),
                             ], logged)
            mop.ref_list = [87654321, 23456]
            self.assertEqual([('Attribute .ref_list deprecated.'
                               ' Use .children instead.',
                               DeprecationWarning, 3),
                             ]*2, logged)
            self.assertEqual([87654321, 23456], mop.children)
            self.assertEqual(2, len(mop))
        finally:
            warn.trap_warnings(old_func)

    def test__getitem__(self):
        mop = self.moc.add(1234567, 'type', 256, children=[0, 255])
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

    def test_parents(self):
        mop = self.moc.add(1234567, 'type', 256, children=[0, 255])
        mop0 = self.moc[0]
        self.assertEqual((), mop0.parents)
        self.assertEqual(0, mop0.num_parents)
        mop255 = self.moc[255]
        self.assertEqual((), mop255.parents)
        self.assertEqual(0, mop255.num_parents)
        mop0.parents = [1234567]
        self.assertEqual(1, mop0.num_parents)
        self.assertEqual([1234567], mop0.parents)
        mop255.parents = [1234567]
        self.assertEqual(1, mop255.num_parents)
        self.assertEqual([1234567], mop255.parents)

    def test_p(self):
        mop = self.moc.add(1234567, 'type', 256, children=[0, 255])
        mop0 = self.moc[0]
        self.assertEqual([], mop0.p)
        mop0.parents = [1234567]
        p = mop0.p
        self.assertEqual(1, len(p))
        self.assertEqual(mop, p[0])

    def test_referrers(self):
        mop = self.moc.add(1234567, 'type', 256, children=[0, 255])
        # Referrers is deprecated
        logged = []
        def log_warn(msg, klass, stacklevel=None):
            logged.append((msg, klass, stacklevel))
        old_func = warn.trap_warnings(log_warn)
        try:
            mop0 = self.moc[0]
            self.assertEqual((), mop0.referrers)
            self.assertEqual([('Attribute .referrers deprecated.'
                               ' Use .parents instead.',
                               DeprecationWarning, 3)
                             ], logged)
            mop0.referrers = [1234567]
            self.assertEqual([('Attribute .referrers deprecated.'
                               ' Use .parents instead.',
                               DeprecationWarning, 3)
                             ]*2, logged)
            self.assertEqual([1234567], mop0.parents)
            del logged[:]
            self.assertEqual(1, mop0.num_referrers)
            self.assertEqual([('Attribute .num_referrers deprecated.'
                               ' Use .num_parents instead.',
                               DeprecationWarning, 3)
                             ], logged)
        finally:
            warn.trap_warnings(old_func)

    def test_parents(self):
        mop = self.moc.add(1234567, 'type', 256, children=[0, 255])
        mop0 = self.moc[0]
        self.assertEqual((), mop0.parents)
        self.assertEqual(0, mop0.num_parents)
        mop255 = self.moc[255]
        self.assertEqual((), mop255.parents)
        self.assertEqual(0, mop255.num_parents)
        mop0.parents = [1234567]
        self.assertEqual(1, mop0.num_parents)
        self.assertEqual([1234567], mop0.parents)
        mop255.parents = [1234567]
        self.assertEqual(1, mop255.num_parents)
        self.assertEqual([1234567], mop255.parents)

    def test__repr__(self):
        mop = self.moc.add(1234, 'str', 24)
        self.assertEqual('str(1234 24B)', repr(mop))
        mop = self.moc.add(1235, 'tuple', 12, [4567, 8900])
        self.assertEqual('tuple(1235 12B 2refs)', repr(mop))
        mop = self.moc.add(1236, 'module', 12, [4568, 8900], name='named')
        # TODO: Will we show the refs? If so, we will want to truncate
        self.assertEqual("module(1236 12B 2refs 'named')", repr(mop))
        mop = self.moc.add(1237, 'module', 12, range(20), name='named')
        self.assertEqual("module(1237 12B 20refs 'named')", repr(mop))
        mop = self.moc.add(1238, 'foo', 12, [10], parent_list=[20, 30])
        self.assertEqual("foo(1238 12B 1refs 2par)", repr(mop))
        mop = self.moc.add(1239, 'str', 24, value='teststr')
        self.assertEqual("str(1239 24B 'teststr')", repr(mop))
        # TODO: Will we want to truncate value?
        mop.value = 'averylongstringwithmorestuff'
        self.assertEqual("str(1239 24B 'averylongstringwithmorestuff')",
                         repr(mop))
        mop = self.moc.add(1240, 'int', 12, value=12345)
        self.assertEqual('int(1240 12B 12345)', repr(mop))
        mop.total_size = 12
        self.assertEqual('int(1240 12B 12345 12.0Btot)', repr(mop))
        mop.total_size = 1024
        self.assertEqual('int(1240 12B 12345 1.0Ktot)', repr(mop))
        mop.total_size = int(1024*1024*10.5)
        self.assertEqual('int(1240 12B 12345 10.5Mtot)', repr(mop))

    def test_expand_refs_as_dict(self):
        self.moc.add(1, 'str', 25, value='a')
        self.moc.add(2, 'int', 12, value=1)
        mop = self.moc.add(3, 'dict', 140, children=[1, 2])
        as_dict = mop.refs_as_dict()
        self.assertEqual({'a': 1}, mop.refs_as_dict())
        # It should even work if there is a 'trailing' entry, as after
        # collapse, instances have the dict inline, and end with the reference
        # to the type
        mop = self.moc.add(4, 'MyClass', 156, children=[2, 1, 8])
        self.assertEqual({1: 'a'}, mop.refs_as_dict())

    def test_expand_refs_as_dict_unknown(self):
        # We only expand objects that fall into known types, not just any value
        mop_f = self.moc.add(1, 'frame', 300, value='func_foo')
        self.moc.add(2, 'str', 25, value='a')
        mop = self.moc.add(3, 'dict', 140, children=[2, 1])
        as_dict = mop.refs_as_dict()
        self.assertEqual({'a': mop_f}, as_dict)

    def assertSizeOf(self, num_words, obj, extra_size=0, has_gc=True):
        expected_size = extra_size + num_words * _scanner._word_size
        if has_gc:
            expected_size += _scanner._gc_head_size
        self.assertEqual(expected_size, _scanner.size_of(obj))

    def test__sizeof__(self):
        mop = self.moc[0]
        # 1: PyType*
        # 2: refcnt
        # 3: collection*
        # 4: _MemObject*
        # 5: _managed_obj *
        # No vtable because we have no cdef functions
        self.assertSizeOf(5, mop, has_gc=True)

    def test__sizeof__managed(self):
        mop = self.moc[0]
        del self.moc[0]
        # If the underlying object has been removed from the collection, then
        # the memory is now being managed by the mop itself. So it grows by:
        # 1: PyObject* address
        # 2: PyObject* type_str
        # 3: long size
        # 4: RefList *child_list
        # 5: PyObject *value
        # 6: RefList *parent_list
        # 7: unsigned long total_size
        # 8: PyObject *proxy
        self.assertSizeOf(5+8, mop, has_gc=True)

    def test_traverse(self):
        # When a Proxied object is removed from its Collection, it becomes
        # owned by the Proxy itself, and should be returned from tp_traverse
        mop = self.moc[0]
        # At this point, moc still controls the _MemObject
        self.assertEqual([self.moc], _scanner.get_referents(mop))
        # But now, it references everything else, too
        del self.moc[0]
        self.assertEqual([self.moc, mop.address, mop.type_str, mop.value],
                         _scanner.get_referents(mop))

    def test_traverse_with_parent_and_children(self):
        mop = self.moc.add(1, 'my_class', 1234, children=[5,6,7],
                           parent_list=[8,9,10], value='test str')
        # While in the moc, the Collection manages the references
        self.assertEqual([self.moc], _scanner.get_referents(mop))
        # But once gone, we refer to everything directly
        del self.moc[1]
        self.assertEqual([self.moc, mop.address, mop.type_str, mop.value,
                          5, 6, 7, 8, 9, 10],
                         _scanner.get_referents(mop))

    def test_compute_total_size(self):
        obj = self.moc.add(1, 'test', 1234, children=[0])
        obj = self.moc.add(2, 'other', 4567, children=[1])
        self.assertEqual(1234+4567+100, obj.compute_total_size())
        self.assertEqual(1234+4567, obj.compute_total_size(excluding=[0]))

    def test_all(self):
        self.moc.add(1, 'foo', 1234, children=[0])
        obj = self.moc.add(2, 'other', 4567, children=[1])
        self.assertEqual([1, 0], [o.address for o in obj.all('foo')])
        self.assertEqual([1],
                         [o.address for o in obj.all('foo', excluding=[0])])
        # Excluding 1 actually prevents us from walking further
        self.assertEqual([],
                         [o.address for o in obj.all('foo', excluding=[1])])


class Test_MemObjectProxyIterRecursiveRefs(tests.TestCase):

    def setUp(self):
        super(Test_MemObjectProxyIterRecursiveRefs, self).setUp()
        self.moc = _loader.MemObjectCollection()
        self.moc.add(1024, 'bar', 200)
        self.moc.add(0, 'foo', 100)
        self.moc.add(255, 'baz', 300)

    def assertIterRecursiveRefs(self, addresses, obj, excluding=None):
        self.assertEqual(addresses,
            [o.address for o in obj.iter_recursive_refs(excluding=excluding)])

    def test_no_refs(self):
        self.assertIterRecursiveRefs([1024], self.moc[1024])

    def test_single_depth_refs(self):
        obj = self.moc.add(1, 'test', 1234, children=[1024])
        self.assertIterRecursiveRefs([1, 1024], obj)

    def test_deep_refs(self):
        obj = self.moc.add(1, '1', 1234, children=[2])
        self.moc.add(2, '2', 1234, children=[3])
        self.moc.add(3, '3', 1234, children=[4])
        self.moc.add(4, '4', 1234, children=[5])
        self.moc.add(5, '5', 1234, children=[6])
        self.moc.add(6, '6', 1234, children=[])
        self.assertIterRecursiveRefs([1, 2, 3, 4, 5, 6], obj)

    def test_self_referenced(self):
        self.moc.add(1, 'test', 1234, children=[1024, 2])
        obj = self.moc.add(2, 'test2', 1234, children=[1])
        self.assertIterRecursiveRefs([2, 1, 1024], obj)

    def test_excluding(self):
        obj = self.moc.add(1, 'test', 1234, children=[1024])
        self.assertIterRecursiveRefs([1], obj, excluding=[1024])

    def test_excluding_nested(self):
        self.moc.add(1, 'test', 1234, children=[1024])
        obj = self.moc.add(2, 'test', 1234, children=[1])
        self.assertIterRecursiveRefs([2, 1, 1024], obj)
        self.assertIterRecursiveRefs([2], obj, excluding=[1])

    def test_excluding_wraparound(self):
        self.moc.add(1, 'test', 1234, children=[1024])
        self.moc.add(2, 'test', 1234, children=[1024])
        obj = self.moc.add(3, 'test', 1234, children=[1, 2])
        self.assertIterRecursiveRefs([3, 2, 1024, 1], obj)
        self.assertIterRecursiveRefs([3, 2, 1024], obj, excluding=[1])
        refed = (o.address for o in self.moc[1].iter_recursive_refs())
        self.assertIterRecursiveRefs([3, 2], obj, excluding=refed)

    def test_excluding_self(self):
        self.assertIterRecursiveRefs([], self.moc[1024], excluding=[1024])
        obj = self.moc.add(1, '1', 1234, children=[1024])
        self.assertIterRecursiveRefs([], obj, excluding=[1])
