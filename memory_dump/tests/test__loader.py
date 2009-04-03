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

"""Pyrex extension for tracking loaded objects"""

from memory_dump import (
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
        self.assertEqual([], mem.ref_list)

    def test_ref_list(self):
        mem = _loader.MemObject(1234, 'tuple', 12, [4567, 8901])
        self.assertEqual([4567, 8901], mem.ref_list)

    def test__repr__(self):
        mem = _loader.MemObject(0x1234, 'tuple', 12, [0x4567, 0x89ab])
        self.assertEqual('MemObject(00001234, tuple, 12 bytes, 2 refs)',
                         repr(mem))
        mem = _loader.MemObject(0x1234, 'module', 12, [0x4567, 0x89ab],
                                name='named')
        self.assertEqual('MemObject(00001234, module, named, 12 bytes'
                         ', 2 refs)', repr(mem))
