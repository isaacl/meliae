# Copyright (C) 2009 Canonical Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU General Public License and
# the GNU Lesser General Public License along with this program.  If
# not, see <http://www.gnu.org/licenses/>.

"""The core routines for scanning python references and dumping memory info."""

cdef extern from "stdio.h":
    ctypedef long size_t
    ctypedef struct FILE:
        pass
    size_t fwrite(void *, size_t, size_t, FILE *)
    size_t fprintf(FILE *, char *, ...)

cdef extern from "Python.h":
    FILE *PyFile_AsFile(object)
    int Py_UNICODE_SIZE
    ctypedef struct PyGC_Head:
        pass

cdef extern from "_scanner_core.h":
    Py_ssize_t _size_of(object c_obj)
    void _dump_object_info(FILE *, object c_obj, object nodump, int recurse)
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


def dump_object_info(object fp, object obj, object nodump=None, int recurse_depth=1):
    cdef FILE *out

    out = PyFile_AsFile(fp)
    if out == NULL:
        raise TypeError('not a file')
    _dump_object_info(out, obj, nodump, recurse_depth)


def get_referents(object obj):
    """Similar to gc.get_referents()

    The main different is that gc.get_referents() only includes items that are
    in the garbage collector. However, we want anything referred to by
    tp_traverse.
    """
    return _get_referents(obj)
