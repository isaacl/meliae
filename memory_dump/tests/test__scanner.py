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

"""Tests for the object scanner."""

from memory_dump import (
    _scanner,
    tests,
    )

class TestSizeOf(tests.TestCase):

    def assertSizeOf(self, num_words, extra_size, obj):
        expected_size = extra_size + num_words * _scanner._word_size
        self.assertEqual(expected_size, _scanner.size_of(obj))

    def test_empty_string(self):
        self.assertSizeOf(6, 0, '')

    def test_short_string(self):
        self.assertSizeOf(6, 1, 'a')

    def test_long_string(self):
        self.assertSizeOf(6, 100*1024, ('abcd'*25)*1024)

    def test_tuple(self):
        self.assertSizeOf(3, 0, ())

    def test_tuple_one(self):
        self.assertSizeOf(3+1, 0, ('a',))

    def test_tuple_n(self):
        self.assertSizeOf(3+3, 0, (1, 2, 3))

    def test_empty_list(self):
        self.assertSizeOf(5, 0, [])

    def test_list_with_one(self):
        self.assertSizeOf(5+1, 0, [1])

    def test_list_with_three(self):
        self.assertSizeOf(5+3, 0, [1, 2, 3])

    def test_list_appended(self):
        # Lists over-allocate when you append to them, we want the *allocated*
        # size
        lst = []
        lst.append(1)
        self.assertSizeOf(5+4, 0, lst)

    def test_empty_set(self):
        self.assertSizeOf(25, 0, set())
        self.assertSizeOf(25, 0, frozenset())

    def test_small_sets(self):
        self.assertSizeOf(25, 0, set(range(1)))
        self.assertSizeOf(25, 0, set(range(2)))
        self.assertSizeOf(25, 0, set(range(3)))
        self.assertSizeOf(25, 0, set(range(4)))
        self.assertSizeOf(25, 0, set(range(5)))
        self.assertSizeOf(25, 0, frozenset(range(3)))

    def test_medium_sets(self):
        self.assertSizeOf(25 + 512*2, 0, set(range(100)))
        self.assertSizeOf(25 + 512*2, 0, frozenset(range(100)))

    def test_empty_dict(self):
        self.assertSizeOf(31, 0, dict())

    def test_small_dict(self):
        self.assertSizeOf(31, 0, dict.fromkeys(range(1)))
        self.assertSizeOf(31, 0, dict.fromkeys(range(2)))
        self.assertSizeOf(31, 0, dict.fromkeys(range(3)))
        self.assertSizeOf(31, 0, dict.fromkeys(range(4)))
        self.assertSizeOf(31, 0, dict.fromkeys(range(5)))

    def test_medium_dict(self):
        self.assertSizeOf(31+512*3, 0, dict.fromkeys(range(100)))

    def test_basic_types(self):
        self.assertSizeOf(106, 0, dict)
        self.assertSizeOf(106, 0, set)
        self.assertSizeOf(106, 0, tuple)

    def test_user_type(self):
        class Foo(object):
            pass
        self.assertSizeOf(106, 0, Foo)

    def test_simple_object(self):
        obj = object()
        self.assertSizeOf(2, 0, obj)

    def test_user_instance(self):
        class Foo(object):
            pass
        # This has a pointer to a dict and a weakref list
        f = Foo()
        self.assertSizeOf(4, 0, f)

    def test_slotted_instance(self):
        class One(object):
            __slots__ = ['one']
        # The basic object plus memory for one member
        self.assertSizeOf(3, 0, One())
        class Two(One):
            __slots__ = ['two']
        self.assertSizeOf(4, 0, Two())

    def test_empty_unicode(self):
        self.assertSizeOf(6, 0, u'')

    def test_small_unicode(self):
        self.assertSizeOf(6, _scanner._unicode_size*1, u'a')
        self.assertSizeOf(6, _scanner._unicode_size*4, u'abcd')
        self.assertSizeOf(6, _scanner._unicode_size*2, u'\xbe\xe5')
