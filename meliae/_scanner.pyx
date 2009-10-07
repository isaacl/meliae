# Copyright (C) 2009 Canonical Ltd
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
        # This must be a callable
        _dump_object_info(<write_callback>_file_io_callback, fp_out, obj,
                          nodump, recurse_depth)
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
