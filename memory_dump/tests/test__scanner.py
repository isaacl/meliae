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

import gc
import tempfile

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

    def test_int(self):
        self.assertSizeOf(3, 0, 1)

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

    def test_None(self):
        self.assertSizeOf(2, 0, None)


def _string_to_json(s):
    out = ['"']
    for c in s:
        if c < '\x1F' or c > '\x7e':
            out.append(r'\u%04x' % ord(c))
        elif c in r'\/"':
            # Simple escape
            out.append('\\' + c)
        else:
            out.append(c)
    out.append('"')
    return ''.join(out)


def _unicode_to_json(u):
    out = ['"']
    for c in u:
        if c < u'\u001F' or c > u'\u007e':
            out.append(r'\u%04x' % ord(c))
        elif c in ur'\/"':
            # Simple escape
            out.append('\\' + str(c))
        else:
            out.append(str(c))
    out.append('"')
    return ''.join(out)


class TestJSONString(tests.TestCase):

    def assertJSONString(self, exp, input):
        self.assertEqual(exp, _string_to_json(input))

    def test_empty_string(self):
        self.assertJSONString('""', '')

    def test_simple_strings(self):
        self.assertJSONString('"foo"', 'foo')
        self.assertJSONString('"aoeu aoeu"', 'aoeu aoeu')

    def test_simple_escapes(self):
        self.assertJSONString(r'"\\x\/y\""', r'\x/y"')

    def test_control_escapes(self):
        self.assertJSONString(r'"\u0000\u0001\u0002"', '\x00\x01\x02')


class TestJSONUnicode(tests.TestCase):

    def assertJSONUnicode(self, exp, input):
        val = _unicode_to_json(input)
        self.assertEqual(exp, val)
        self.assertTrue(isinstance(val, str))

    def test_empty(self):
        self.assertJSONUnicode('""', u'')

    def test_ascii_chars(self):
        self.assertJSONUnicode('"abcdefg"', u'abcdefg')

    def test_unicode_chars(self):
        self.assertJSONUnicode(r'"\u0012\u00b5\u2030"', u'\x12\xb5\u2030')

    def test_simple_escapes(self):
        self.assertJSONUnicode(r'"\\x\/y\""', ur'\x/y"')



# A pure python implementation of dump_object_info
def _py_dump_json_obj(obj):
    content = [(
        '{"address": %d'
        ', "type": %s'
        ', "size": %d'
        ) % (id(obj), _string_to_json(obj.__class__.__name__),
             _scanner.size_of(obj))
        ]
    name = getattr(obj, '__name__', None)
    if name is not None:
        content.append(', "name": %s' % (_string_to_json(name),))
    first = True
    content.append(', "refs": [')
    ref_strs = []
    for ref in gc.get_referents(obj):
        ref_strs.append('%d' % (id(ref),))
    content.append(', '.join(ref_strs))
    content.append(']')
    if isinstance(obj, str):
        content.append(', "value": %s' % (_string_to_json(obj[:100]),))
    elif isinstance(obj, unicode):
        content.append(', "value": %s' % (_unicode_to_json(obj[:100]),))
    content.append('}\n')
    return ''.join(content)


def py_dump_object_info(obj):
    obj_info = _py_dump_json_obj(obj)
    # Now we walk again, for certain types we dump them directly
    child_vals = []
    for ref in gc.get_referents(obj):
        if (isinstance(ref, (str, unicode))
            or ref is None
            or type(ref) is object):
            # These types have no traverse func, so we dump them right away
            child_vals.append(_py_dump_json_obj(ref))
    return obj_info + ''.join(child_vals)


class TestPyDumpJSONObj(tests.TestCase):

    def assertDumpText(self, expected, obj):
        self.assertEqual(expected, _py_dump_json_obj(obj))

    def test_str(self):
        mystr = 'a string'
        self.assertDumpText(
            '{"address": %d, "type": "str", "size": %d, "refs": []'
            ', "value": "a string"}\n' % (id(mystr), _scanner.size_of(mystr)),
            mystr)

    def test_unicode(self):
        myu = u'a \xb5nicode'
        self.assertDumpText(
            '{"address": %d, "type": "unicode", "size": %d, "refs": []'
            ', "value": "a \\u00b5nicode"}\n' % (
                id(myu), _scanner.size_of(myu)),
            myu)

    def test_obj(self):
        obj = object()
        self.assertDumpText(
            '{"address": %d, "type": "object", "size": %d, "refs": []}\n'
            % (id(obj), _scanner.size_of(obj)), obj)

    def test_tuple(self):
        a = object()
        b = object()
        t = (a, b)
        self.assertDumpText(
            '{"address": %d, "type": "tuple", "size": %d'
            ', "refs": [%d, %d]}\n'
            % (id(t), _scanner.size_of(t), id(b), id(a)), t)

    def test_module(self):
        m = _scanner
        self.assertDumpText(
            '{"address": %d, "type": "module", "size": %d'
            ', "name": "memory_dump._scanner", "refs": [%d]}\n'
            % (id(m), _scanner.size_of(m), id(m.__dict__)), m)


class TestDumpInfo(tests.TestCase):
    """dump_object_info should give the same result at py_dump_object_info"""

    def assertDumpInfo(self, obj):
        t = tempfile.TemporaryFile(prefix='memory_dump-')
        # On some platforms TemporaryFile returns a wrapper object with 'file'
        # being the real object, on others, the returned object *is* the real
        # file object
        t_file = getattr(t, 'file', t)
        _scanner.dump_object_info(t_file, obj)
        t.seek(0)
        self.assertEqual(py_dump_object_info(obj), t.read())

    def test_dump_int(self):
        self.assertDumpInfo(1)

    def test_dump_tuple(self):
        obj1 = object()
        obj2 = object()
        t = (obj1, obj2)
        self.assertDumpInfo(t)

    def test_dump_dict(self):
        key = object()
        val = object()
        d = {key: val}
        self.assertDumpInfo(d)

    def test_class(self):
        class Foo(object):
            pass
        class Child(Foo):
            pass
        self.assertDumpInfo(Child)

    def test_module(self):
        self.assertDumpInfo(_scanner)

    def test_instance(self):
        class Foo(object):
            pass
        f = Foo()
        self.assertDumpInfo(f)

    def test_slot_instance(self):
        class One(object):
            __slots__ = ['one']
        one = One()
        one.one = object()
        self.assertDumpInfo(one)

        class Two(One):
            __slots__ = ['two']
        two = Two()
        two.one = object()
        two.two = object()
        self.assertDumpInfo(two)

    def test_None(self):
        self.assertDumpInfo(None)

    def test_str(self):
        self.assertDumpInfo('this is a short string\n')

    def test_long_str(self):
        self.assertDumpInfo('abcd'*1000)

    def test_unicode(self):
        self.assertDumpInfo(u'this is a short string\n')

    def test_long_unicode(self):
        self.assertDumpInfo(u'abcd'*1000)
