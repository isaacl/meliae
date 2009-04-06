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

"""Test the Set of Integers object."""

from memory_dump import (
    _intset,
    tests,
    )


class TestIntSet(tests.TestCase):

    def test__init__(self):
        s = _intset.IntSet()

    def test__len__(self):
        self.assertEqual(0, len(_intset.IntSet()))

    def test__contains__(self):
        iset = _intset.IntSet()
        self.assertFalse(0 in iset)

    def test__contains__not_int(self):
        iset = _intset.IntSet()
        def test_contain():
            return 'a' in iset
        self.assertRaises(TypeError, test_contain)

    def test_add_singletons(self):
        iset = _intset.IntSet()
        iset.add(-1)
        self.assertTrue(-1 in iset)
        self.assertEqual(1, len(iset))
        iset.add(-2)
        self.assertTrue(-2 in iset)
        self.assertEqual(2, len(iset))

    def test_add_not_int(self):
        iset = _intset.IntSet()
        self.assertRaises(TypeError, iset.add, 'foo')

    def test_add_general(self):
        iset = _intset.IntSet()
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
        iset = _intset.IntSet()
        for i in xrange(10000):
            iset.add(i)
        self.assertEqual(10000, len(iset))

    def test_from_list(self):
        iset = _intset.IntSet([-1, 0, 1, 2, 3, 4])
        self.assertTrue(-1 in iset)
        self.assertTrue(0 in iset)
        self.assertTrue(1 in iset)
        self.assertTrue(2 in iset)
        self.assertTrue(3 in iset)
        self.assertTrue(4 in iset)
        self.assertFalse(5 in iset)

    def test_discard(self):
        # Not supported yet... KnownFailure
        pass

    def test_remove(self):
        # Not supported yet... KnownFailure
        pass


class TestIDSet(TestIntSet):
    pass
