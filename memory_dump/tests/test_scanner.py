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

"""The core routines for scanning python references and dumping memory info."""

import tempfile

from memory_dump import (
    scanner,
    tests,
    )
from memory_dump.tests import test__scanner


class TestDumpAllReferenced(tests.TestCase):

    def assertDumpAllReferenced(self, ref_objs, obj):
        t = tempfile.TemporaryFile(prefix='memory_dump-')
        # On some platforms TemporaryFile returns a wrapper object with 'file'
        # being the real object, on others, the returned object *is* the real
        # file object
        t_file = getattr(t, 'file', t)
        scanner.dump_all_referenced(t_file, obj)
        t.flush()
        t.seek(0)
        # We don't care if the same entries are printed multiple times, just
        # that they are all correct
        lines = set(t.readlines())
        # py_dump_object_info will create a string that covers multpile lines,
        # so we need to split it back into 1-line-per-record
        ref_lines = [test__scanner.py_dump_object_info(ref_obj)
                     for ref_obj in ref_objs]
        ref_lines = set(''.join(ref_lines).splitlines(True))
        self.assertEqual(sorted(ref_lines), sorted(lines))

    def test_dump_str(self):
        s = 'a test string'
        self.assertDumpAllReferenced([s], s)

    def test_dump_obj(self):
        o = object()
        self.assertDumpAllReferenced([o], o)

    def test_dump_simple_tuple(self):
        k = 10245
        v = 'a value string'
        t = (k, v)
        self.assertDumpAllReferenced([k, v, t], t)

    def test_dump_list_of_tuple(self):
        k = 10245
        v = 'a value string'
        t = (k, v)
        l = [k, v, t]
        self.assertDumpAllReferenced([k, v, l, t], l)

    def test_dump_recursive(self):
        a = 1
        b = 'str'
        c = {}
        l = [a, b, c]
        c[a] = l
        # We have a reference cycle here, but we should not loop endlessly :)
        self.assertDumpAllReferenced([a, b, c, l], l)
        self.assertDumpAllReferenced([a, b, c, l], c)
