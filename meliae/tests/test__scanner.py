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

"""Tests for the object scanner."""

import gc
import sys
import tempfile
import types
import zlib

from meliae import (
    _scanner,
    tests,
    )


STRING_BASE = 8
STRING_SCALING = 4
if sys.version_info[:2] >= (2, 7):
    # In python2.7 they 'shrunk' strings by a couple bytes, by changing where
    # the pointer was. So their base size is a few bytes smaller
    STRING_BASE = 5


class TestSizeOf(tests.TestCase):

    def assertSizeOf(self, num_words, obj, extra_size=0, has_gc=True):
        expected_size = extra_size + num_words * _scanner._word_size
        if has_gc:
            expected_size += _scanner._gc_head_size
        self.assertEqual(expected_size, _scanner.size_of(obj))

    def test_empty_string(self):
        fixed_size = STRING_BASE
        self.assertSizeOf(STRING_SCALING, '', extra_size=0+STRING_BASE, has_gc=False)

    def test_short_string(self):
        self.assertSizeOf(STRING_SCALING, 'a', extra_size=1+STRING_BASE, has_gc=False)

    def test_long_string(self):
        self.assertSizeOf(STRING_SCALING, ('abcd'*25)*1024,
                          extra_size=100*1024+STRING_BASE, has_gc=False)

    def test_tuple(self):
        self.assertSizeOf(3, ())

    def test_tuple_one(self):
        self.assertSizeOf(3+1, ('a',))

    def test_tuple_n(self):
        self.assertSizeOf(3+3, (1, 2, 3))

    def test_empty_list(self):
        self.assertSizeOf(5, [])

    def test_list_with_one(self):
        self.assertSizeOf(5+1, [1])

    def test_list_with_three(self):
        self.assertSizeOf(5+3, [1, 2, 3])

    def test_int(self):
        self.assertSizeOf(3, 1, has_gc=False)

    def test_list_appended(self):
        # Lists over-allocate when you append to them, we want the *allocated*
        # size
        lst = []
        lst.append(1)
        self.assertSizeOf(5+4, lst)

    def test_empty_set(self):
        self.assertSizeOf(25, set())
        self.assertSizeOf(25, frozenset())

    def test_small_sets(self):
        self.assertSizeOf(25, set(range(1)))
        self.assertSizeOf(25, set(range(2)))
        self.assertSizeOf(25, set(range(3)))
        self.assertSizeOf(25, set(range(4)))
        self.assertSizeOf(25, set(range(5)))
        self.assertSizeOf(25, frozenset(range(3)))

    def test_medium_sets(self):
        self.assertSizeOf(25 + 512*2, set(range(100)))
        self.assertSizeOf(25 + 512*2, frozenset(range(100)))

    def test_empty_dict(self):
        self.assertSizeOf(31, dict())

    def test_small_dict(self):
        self.assertSizeOf(31, dict.fromkeys(range(1)))
        self.assertSizeOf(31, dict.fromkeys(range(2)))
        self.assertSizeOf(31, dict.fromkeys(range(3)))
        self.assertSizeOf(31, dict.fromkeys(range(4)))
        self.assertSizeOf(31, dict.fromkeys(range(5)))

    def test_medium_dict(self):
        self.assertSizeOf(31+512*3, dict.fromkeys(range(100)))

    def test_basic_types(self):
        type_size = 106
        if sys.version_info[:2] >= (2, 6):
            type_size = 109
        self.assertSizeOf(type_size, dict)
        self.assertSizeOf(type_size, set)
        self.assertSizeOf(type_size, tuple)

    def test_user_type(self):
        class Foo(object):
            pass
        if sys.version_info[:2] >= (2, 6):
            self.assertSizeOf(109, Foo)
        else:
            self.assertSizeOf(106, Foo)

    def test_simple_object(self):
        obj = object()
        self.assertSizeOf(2, obj, has_gc=False)

    def test_user_instance(self):
        class Foo(object):
            pass
        # This has a pointer to a dict and a weakref list
        f = Foo()
        self.assertSizeOf(4, f)

    def test_slotted_instance(self):
        class One(object):
            __slots__ = ['one']
        # The basic object plus memory for one member
        self.assertSizeOf(3, One())
        class Two(One):
            __slots__ = ['two']
        self.assertSizeOf(4, Two())

    def test_empty_unicode(self):
        self.assertSizeOf(6, u'', extra_size=0, has_gc=False)

    def test_small_unicode(self):
        self.assertSizeOf(6, u'a', extra_size=_scanner._unicode_size*1,
                          has_gc=False)
        self.assertSizeOf(6, u'abcd', extra_size=_scanner._unicode_size*4,
                          has_gc=False)
        self.assertSizeOf(6, u'\xbe\xe5', extra_size=_scanner._unicode_size*2,
                          has_gc=False)

    def test_None(self):
        self.assertSizeOf(2, None, has_gc=False)

    def test__sizeof__instance(self):
        # __sizeof__ appears to have been introduced in python 2.6, and
        # is meant to return the number of bytes allocated to this
        # object. It does not include GC overhead, that seems to be added back
        # in as part of sys.getsizeof(). So meliae does the same in size_of()
        class CustomSize(object):
            def __init__(self, size):
                self.size = size
            def __sizeof__(self):
                return self.size
        self.assertSizeOf(0, CustomSize(10), 10, has_gc=True)
        self.assertSizeOf(0, CustomSize(20), 20, has_gc=True)
        # If we get '-1' as the size we assume something is wrong, and fall
        # back to the original size
        self.assertSizeOf(4, CustomSize(-1), has_gc=True)

    def test_size_of_special(self):
        class CustomWithoutSizeof(object):
            pass
        log = []
        def _size_32(obj):
            log.append(obj)
            return 800
        def _size_64(obj):
            log.append(obj)
            return 1600
            
        obj = CustomWithoutSizeof()
        self.assertSizeOf(4, obj)
        _scanner.add_special_size('CustomWithoutSizeof', _size_32, _size_64)
        try:
            self.assertSizeOf(200, obj)
        finally:
            _scanner.add_special_size('CustomWithoutSizeof', None, None)
        self.assertEqual([obj], log)
        del log[:]
        self.assertSizeOf(4, obj)
        self.assertEqual([], log)

    def test_size_of_special_neg1(self):
        # Returning -1 falls back to the regular __sizeof__, etc interface
        class CustomWithoutSizeof(object):
            pass
        log = []
        def _size_neg1(obj):
            log.append(obj)
            return -1
        obj = CustomWithoutSizeof()
        self.assertSizeOf(4, obj)
        _scanner.add_special_size('CustomWithoutSizeof', _size_neg1, _size_neg1)
        try:
            self.assertSizeOf(4, obj)
        finally:
            _scanner.add_special_size('CustomWithoutSizeof', None, None)
        self.assertEqual([obj], log)

    def test_size_of_zlib_compress_obj(self):
        # zlib compress objects allocate a lot of extra buffers, we want to
        # track that. Note that we are approximating it, because we don't
        # actually inspect the C attributes. But it is a closer approximation
        # than not doing this.
        c = zlib.compressobj()
        self.assertTrue(_scanner.size_of(c) > 256000)
        self.assertEqual(0, _scanner.size_of(c) % _scanner._word_size)

    def test_size_of_zlib_decompress_obj(self):
        d = zlib.decompressobj()
        self.assertTrue(_scanner.size_of(d) > 30000)
        self.assertEqual(0, _scanner.size_of(d) % _scanner._word_size)


def _string_to_json(s):
    out = ['"']
    for c in s:
        if c <= '\x1f' or c > '\x7e':
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
        if c <= u'\u001f' or c > u'\u007e':
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
        self.assertJSONString(r'"\u0000\u0001\u0002\u001f"', '\x00\x01\x02\x1f')


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
        self.assertJSONUnicode(r'"\u0012\u00b5\u2030\u001f"',
                               u'\x12\xb5\u2030\x1f')

    def test_simple_escapes(self):
        self.assertJSONUnicode(r'"\\x\/y\""', ur'\x/y"')


# A pure python implementation of dump_object_info
def _py_dump_json_obj(obj):
    klass = getattr(obj, '__class__', None)
    if klass is None:
        # This is an old style class
        klass = type(obj)
    content = [(
        '{"address": %d'
        ', "type": %s'
        ', "size": %d'
        ) % (id(obj), _string_to_json(klass.__name__),
             _scanner.size_of(obj))
        ]
    name = getattr(obj, '__name__', None)
    if name is not None:
        content.append(', "name": %s' % (_string_to_json(name),))
    if getattr(obj, '__len__', None) is not None:
        content.append(', "len": %s' % (len(obj),))
    if isinstance(obj, str):
        content.append(', "value": %s' % (_string_to_json(obj[:100]),))
    elif isinstance(obj, unicode):
        content.append(', "value": %s' % (_unicode_to_json(obj[:100]),))
    elif obj is True:
        content.append(', "value": "True"')
    elif obj is False:
        content.append(', "value": "False"')
    elif isinstance(obj, int):
        content.append(', "value": %d' % (obj,))
    elif isinstance(obj, types.FrameType):
        content.append(', "value": "%s"' % (obj.f_code.co_name,))
    first = True
    content.append(', "refs": [')
    ref_strs = []
    for ref in gc.get_referents(obj):
        ref_strs.append('%d' % (id(ref),))
    content.append(', '.join(ref_strs))
    content.append(']')
    content.append('}\n')
    return ''.join(content)


def py_dump_object_info(obj, nodump=None):
    if nodump is not None:
        if obj is nodump:
            return ''
        try:
            if obj in nodump:
                return ''
        except TypeError:
            # This is probably an 'unhashable' object, which means it can't be
            # put into a set, and thus we are sure it isn't in the 'nodump'
            # set.
            pass
    obj_info = _py_dump_json_obj(obj)
    # Now we walk again, for certain types we dump them directly
    child_vals = []
    for ref in gc.get_referents(obj):
        if (isinstance(ref, (str, unicode, int, types.CodeType))
            or ref is None
            or type(ref) is object):
            # These types have no traverse func, so we dump them right away
            if nodump is None or ref not in nodump:
                child_vals.append(_py_dump_json_obj(ref))
    return obj_info + ''.join(child_vals)


class TestPyDumpJSONObj(tests.TestCase):

    def assertDumpText(self, expected, obj):
        self.assertEqual(expected, _py_dump_json_obj(obj))

    def test_str(self):
        mystr = 'a string'
        self.assertDumpText(
            '{"address": %d, "type": "str", "size": %d, "len": 8'
            ', "value": "a string", "refs": []}\n'
            % (id(mystr), _scanner.size_of(mystr)),
            mystr)
        mystr = 'a \\str/with"control'
        self.assertDumpText(
            '{"address": %d, "type": "str", "size": %d, "len": 19'
            ', "value": "a \\\\str\\/with\\"control", "refs": []}\n'
            % (id(mystr), _scanner.size_of(mystr)),
            mystr)

    def test_unicode(self):
        myu = u'a \xb5nicode'
        self.assertDumpText(
            '{"address": %d, "type": "unicode", "size": %d'
            ', "len": 9, "value": "a \\u00b5nicode", "refs": []}\n' % (
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
            ', "len": 2, "refs": [%d, %d]}\n'
            % (id(t), _scanner.size_of(t), id(b), id(a)), t)

    def test_module(self):
        m = _scanner
        self.assertDumpText(
            '{"address": %d, "type": "module", "size": %d'
            ', "name": "meliae._scanner", "refs": [%d]}\n'
            % (id(m), _scanner.size_of(m), id(m.__dict__)), m)

    def test_bool(self):
        a = True
        b = False
        self.assertDumpText(
            '{"address": %d, "type": "bool", "size": %d'
            ', "value": "True", "refs": []}\n'
            % (id(a), _scanner.size_of(a)), a)
        self.assertDumpText(
            '{"address": %d, "type": "bool", "size": %d'
            ', "value": "False", "refs": []}\n'
            % (id(b), _scanner.size_of(b)), b)


class TestDumpInfo(tests.TestCase):
    """dump_object_info should give the same result at py_dump_object_info"""

    def assertDumpInfo(self, obj, nodump=None):
        t = tempfile.TemporaryFile(prefix='meliae-')
        # On some platforms TemporaryFile returns a wrapper object with 'file'
        # being the real object, on others, the returned object *is* the real
        # file object
        t_file = getattr(t, 'file', t)
        _scanner.dump_object_info(t_file, obj, nodump=nodump)
        t.seek(0)
        as_bytes = t.read()
        self.assertEqual(py_dump_object_info(obj, nodump=nodump), as_bytes)
        as_list = []
        _scanner.dump_object_info(as_list.append, obj, nodump=nodump)
        self.assertEqual(as_bytes, ''.join(as_list))

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
        self.assertDumpInfo('this is a short \x00 \x1f \xffstring\n')
        self.assertDumpInfo('a \\string / with " control chars')

    def test_long_str(self):
        self.assertDumpInfo('abcd'*1000)

    def test_unicode(self):
        self.assertDumpInfo(u'this is a short \u1234 \x00 \x1f \xffstring\n')

    def test_long_unicode(self):
        self.assertDumpInfo(u'abcd'*1000)

    def test_nodump(self):
        self.assertDumpInfo(None, nodump=set([None]))

    def test_ref_nodump(self):
        self.assertDumpInfo((None, None), nodump=set([None]))

    def test_nodump_the_nodump(self):
        nodump = set([None, 1])
        t = (20, nodump)
        self.assertDumpInfo(t, nodump=nodump)

    def test_function(self):
        def myfunction():
            pass
        self.assertDumpInfo(myfunction)

    def test_class(self):
        class MyClass(object):
            pass
        self.assertDumpInfo(MyClass, nodump=set([object]))
        inst = MyClass()
        self.assertDumpInfo(inst)

    def test_old_style_class(self):
        class MyOldClass:
            pass
        self.assertDumpInfo(MyOldClass)

    def test_bool(self):
        self.assertDumpInfo(True)
        self.assertDumpInfo(False)

    def test_frame(self):
        def local_frame():
            f = sys._getframe()
            return f
        f = local_frame()
        self.assertDumpInfo(f)


class TestGetReferents(tests.TestCase):

    def test_list_referents(self):
        l = ['one', 2, object(), 4.0]
        self.assertEqual(gc.get_referents(l), _scanner.get_referents(l))
