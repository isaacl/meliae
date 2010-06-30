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
