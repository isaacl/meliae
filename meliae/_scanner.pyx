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

"""The core routines for scanning python references and dumping memory info."""

cdef extern from "stdio.h":
    ctypedef long size_t
    ctypedef struct FILE:
        pass
    FILE *stderr
    size_t fwrite(void *, size_t, size_t, FILE *)
    size_t fprintf(FILE *, char *, ...)
    void fflush(FILE *)

cdef extern from "Python.h":
    FILE *PyFile_AsFile(object)
    int Py_UNICODE_SIZE
    ctypedef struct PyGC_Head:
        pass
    object PyString_FromStringAndSize(char *, Py_ssize_t)


cdef extern from "_scanner_core.h":
    Py_ssize_t _size_of(object c_obj)
    ctypedef void (*write_callback)(void *callee_data, char *bytes, size_t len)

    void _clear_last_dumped()
    void _dump_object_info(write_callback write, void *callee_data,
                           object c_obj, object nodump, int recurse)
    object _get_referents(object c_obj)
    object _get_special_case_dict()


_word_size = sizeof(Py_ssize_t)
_gc_head_size = sizeof(PyGC_Head)
_unicode_size = Py_UNICODE_SIZE


def size_of(obj):
    """Compute the size of the object.

    This is the actual malloc() size for this object, so for dicts it is the
    size of the dict object, plus the size of the array of references, but
    *not* the size of each individual referenced object.

    :param obj: The object to measure
    :return: An integer of the number of bytes used by this object.
    """
    return _size_of(obj)


cdef void _file_io_callback(void *callee_data, char *bytes, size_t len):
    cdef FILE *file_cb

    file_cb = <FILE *>callee_data
    fwrite(bytes, 1, len, file_cb)


cdef void _callable_callback(void *callee_data, char *bytes, size_t len):
    callable = <object>callee_data

    s = PyString_FromStringAndSize(bytes, len)
    callable(s)


def dump_object_info(object out, object obj, object nodump=None,
                     int recurse_depth=1):
    """Dump the object information to the given output.

    :param out: Either a File object, or a callable.
        If a File object, we will write bytes to the underlying FILE*
        Otherwise, we will call(str) with bytes as we build up the state of the
        object. Note that a single call will not be a complete description, but
        potentially a single character of the final formatted string.
    :param obj: The object to inspect
    :param nodump: If supplied, this is a set() of objects that we want to
        exclude from the dump file.
    :param recurse_depth: 0 to only dump the supplied object
       1 to dump the object and immediate neighbors that would not otherwise be
       referenced (such as strings).
       2 dump everything we find and continue recursing
    """
    cdef FILE *fp_out

    fp_out = PyFile_AsFile(out)
    if fp_out != NULL:
        _dump_object_info(<write_callback>_file_io_callback, fp_out, obj,
                          nodump, recurse_depth)
        fflush(fp_out)
    else:
        _dump_object_info(<write_callback>_callable_callback, <void *>out, obj,
                          nodump, recurse_depth)
    _clear_last_dumped()


def get_referents(object obj):
    """Similar to gc.get_referents()

    The main different is that gc.get_referents() only includes items that are
    in the garbage collector. However, we want anything referred to by
    tp_traverse.
    """
    return _get_referents(obj)


def add_special_size(object tp_name, object size_of_32, object size_of_64):
    """Special case a given object size.

    This is only meant to be used for objects we don't already handle or which
    don't implement __sizeof__ (those are checked before this check happens).

    This is meant for things like zlib.Compress which allocates a lot of
    internal buffers, which are not easily accessible (but can be
    approximated).  The gc header should not be included in this size, it will
    be added at runtime.

    Setting the value to None will remove the value.

    (We only distinguish size_of_32 from size_of_64 for the implementer's
    benefit, since sizeof() is not generally accessible from Python.)

    :param tp_name: The type string we care about (such as 'zlib.Compress').
        This will be matched against object->type->tp_name.
    :param size_of_32: Called when _word_size == 32-bits
    :param size_of_64: Called when _word_size == 64-bits
    :return: None
    """
    special_dict = _get_special_case_dict()
    if _word_size == 4:
        sz = size_of_32
    elif _word_size == 8:
        sz = size_of_64
    else:
        raise RuntimeError('Unknown word size: %s' % (_word_size,))
    if sz is None:
        if tp_name in special_dict:
            del special_dict[tp_name]
    else:
        special_dict[tp_name] = sz


def _zlib_size_of_32(zlib_obj):
    """Return a __sizeof__ for a zlib object."""
    t = type(zlib_obj)
    name = t.__name__
    if name.endswith('Compress'):
        pass
    elif name.endswith('Decompress'):
        pass
    else:
        return -1


def _zlib_size_of_64(zlib_obj):
    """Return a __sizeof__ for a zlib object."""
    t = type(zlib_obj)
    name = t.__name__
    if name.endswith('Compress'):
        pass
    elif name.endswith('Decompress'):
        pass
    else:
        return -1

add_special_size('zlib.Compress', _zlib_size_of_32, _zlib_size_of_64)
add_special_size('zlib.Decompress', _zlib_size_of_32, _zlib_size_of_64)
