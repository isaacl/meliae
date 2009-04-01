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
