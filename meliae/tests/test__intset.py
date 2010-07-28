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

"""Test the Set of Integers object."""

import sys

from meliae import (
    _intset,
    _scanner,
    tests,
    )


class TestIntSet(tests.TestCase):

    _set_type = _intset.IntSet

    def test__init__(self):
        s = self._set_type()

    def test__len__(self):
        self.assertEqual(0, len(self._set_type()))

    def test__contains__(self):
        iset = self._set_type()
        self.assertFalse(0 in iset)

    def test__contains__not_int(self):
        iset = self._set_type()
        def test_contain():
            return 'a' in iset
        self.assertRaises(TypeError, test_contain)

    def test_add_singletons(self):
        iset = self._set_type()
        iset.add(-1)
        self.assertTrue(-1 in iset)
        self.assertEqual(1, len(iset))
        iset.add(-2)
        self.assertTrue(-2 in iset)
        self.assertEqual(2, len(iset))

    def test_add_not_int(self):
        iset = self._set_type()
        self.assertRaises(TypeError, iset.add, 'foo')

    def test_add_general(self):
        iset = self._set_type()
        self.assertEqual(0, len(iset))
        self.assertFalse(1 in iset)
        self.assertFalse(2 in iset)
        self.assertFalse(128 in iset)
        self.assertFalse(129 in iset)
        self.assertFalse(130 in iset)
        iset.add(1)
        self.assertEqual(1, len(iset))
        self.assertTrue(1 in iset)
        self.assertFalse(2 in iset)
        self.assertFalse(128 in iset)
        self.assertFalse(129 in iset)
        self.assertFalse(130 in iset)
        iset.add(2)
        self.assertEqual(2, len(iset))
        self.assertTrue(1 in iset)
        self.assertTrue(2 in iset)
        self.assertFalse(128 in iset)
        self.assertFalse(129 in iset)
        self.assertFalse(130 in iset)
        iset.add(129)
        self.assertTrue(1 in iset)
        self.assertTrue(2 in iset)
        self.assertFalse(128 in iset)
        self.assertTrue(129 in iset)
        self.assertFalse(130 in iset)

    def test_add_and_grow(self):
        iset = self._set_type()
        for i in xrange(0, 10000):
            iset.add(i)
        self.assertEqual(10000, len(iset))

    def test_from_list(self):
        iset = self._set_type([0, 1, 2, 3, 4, 5])
        self.assertTrue(0 in iset)
        self.assertTrue(1 in iset)
        self.assertTrue(2 in iset)
        self.assertTrue(3 in iset)
        self.assertTrue(4 in iset)
        self.assertTrue(5 in iset)
        self.assertFalse(6 in iset)

    def test_discard(self):
        # Not supported yet... KnownFailure
        pass

    def test_remove(self):
        # Not supported yet... KnownFailure
        pass

    def assertSizeOf(self, num_words, obj, extra_size=0, has_gc=True):
        expected_size = extra_size + num_words * _scanner._word_size
        if has_gc:
            expected_size += _scanner._gc_head_size
        self.assertEqual(expected_size, _scanner.size_of(obj))

    def test__sizeof__(self):
        # The intset class should report a size
        iset = self._set_type([])
        # I'm a bit leery of has_gc=False, as I think some versions of pyrex
        # will put the object into GC even though it doesn't have any 'object'
        # references...
        # We could do something with a double-entry check
        # Size is:
        # 1: PyType*
        # 2: refcnt
        # 3: vtable*
        # 4: _count
        # 5: _mask
        # 6: _array
        # 4-byte int _has_singleton
        self.assertSizeOf(6, iset, extra_size=4, has_gc=False)
        iset.add(12345)
        # Min allocation is 256 entries
        self.assertSizeOf(6+256, iset, extra_size=4, has_gc=False)


class TestIDSet(TestIntSet):

    _set_type = _intset.IDSet

    def test_high_bit(self):
        # Python ids() are considered to be unsigned values, but python
        # integers are considered to be signed longs. As such, we need to play
        # some tricks to get them to fit properly. Otherwise we get
        # 'Overflow' exceptions
        bigint = sys.maxint + 1
        self.assertTrue(isinstance(bigint, long))
        iset = self._set_type()
        self.assertFalse(bigint in iset)
        iset.add(bigint)
        self.assertTrue(bigint in iset)
        
    def test_add_singletons(self):
        pass
        # Negative values cannot be checked in IDSet, because we cast them to
        # unsigned long first.
