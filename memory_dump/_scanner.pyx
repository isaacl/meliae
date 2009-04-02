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

cdef extern from "stdio.h":
    ctypedef long size_t
    ctypedef struct FILE:
        pass
    size_t fwrite(void *, size_t, size_t, FILE *)
    size_t fprintf(FILE *, char *, ...)

cdef extern from "Python.h":
    struct _object

    ctypedef int (*visitproc)(_object *, void *)
    ctypedef int (*traverseproc)(_object *, visitproc, void *)

    struct _typeobject:
        char * tp_name
        Py_ssize_t tp_basicsize
        Py_ssize_t tp_itemsize
        traverseproc tp_traverse

    struct _object:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type

    ctypedef _object PyObject

    ctypedef struct PyVarObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t ob_size

    ctypedef struct PyListObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t allocated

    ctypedef struct setentry:
        pass

    ctypedef struct PySetObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t mask
        setentry *table
        setentry *smalltable

    ctypedef struct PyDictEntry:
        pass

    ctypedef struct PyDictObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t ma_mask
        Py_ssize_t ma_table
        Py_ssize_t ma_smalltable

    ctypedef struct PyUnicodeObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t length

    FILE *PyFile_AsFile(object)

    int Py_UNICODE_SIZE
    ctypedef int Py_UNICODE

    char *PyString_AS_STRING(PyObject *)
    Py_ssize_t PyString_GET_SIZE(PyObject *)

    int PyString_Check(PyObject *)
    int PyList_Check(PyObject *)
    int PyAnySet_Check(PyObject *)
    int PyDict_Check(PyObject *)
    int PyUnicode_Check(PyObject *)
    Py_UNICODE *PyUnicode_AS_UNICODE(PyObject *)
    Py_ssize_t PyUnicode_GET_SIZE(PyObject *)

cdef extern from "_scanner_core.h":
    Py_ssize_t _size_of(PyObject *c_obj)


_word_size = sizeof(Py_ssize_t)
_unicode_size = Py_UNICODE_SIZE


def size_of(obj):
    """Compute the size of the object.

    This is the actual malloc() size for this object, so for dicts it is the
    size of the dict object, plus the size of the array of references, but
    *not* the size of each individual referenced object.

    :param obj: The object to measure
    :return: An integer of the number of bytes used by this object.
    """
    return _size_of(<PyObject *>obj)


cdef int _dump_reference(PyObject *c_obj, void* val):
    cdef FILE *out
    out = <FILE *>val
    fprintf(out, " 0x%08lx", <long>c_obj)
    return 0


cdef void _dump_string(FILE *out, PyObject *c_obj):
    # TODO: consider writing to a small memory buffer, before writing to disk
    cdef Py_ssize_t str_size
    cdef char *str_buf
    cdef Py_ssize_t i

    str_buf = PyString_AS_STRING(c_obj)
    str_size = PyString_GET_SIZE(c_obj)

    # Never try to dump more than this many chars
    if str_size > 100:
        str_size = 100
    fprintf(out, " s ")
    for i from 0 <= i < str_size:
        fprintf(out, "%02x", <int>str_buf[i])


cdef void _dump_unicode(FILE *out, PyObject *c_obj):
    # TODO: consider writing to a small memory buffer, before writing to disk
    cdef Py_ssize_t uni_size
    cdef Py_UNICODE *uni_buf
    cdef Py_ssize_t i

    uni_buf = PyUnicode_AS_UNICODE(c_obj)
    uni_size = PyUnicode_GET_SIZE(c_obj)

    # Never try to dump more than this many chars
    if uni_size > 100:
        uni_size = 100
    fprintf(out, " u ")
    for i from 0 <= i < uni_size:
        fprintf(out, "%08x", <unsigned int>uni_buf[i])


cdef int _dump_if_no_traverse(PyObject *c_obj, void* val):
    cdef FILE *out
    if c_obj.ob_type.tp_traverse != NULL:
        return 0
    out = <FILE *>val
    # We know that it is safe to recurse here, because tp_traverse is NULL
    _dump_object_info(out, c_obj)
    return 0


cdef void _dump_object_info(FILE *out, PyObject * c_obj):
    cdef Py_ssize_t size

    size = _size_of(c_obj)
    fprintf(out, "0x%08lx %s %d", <long>c_obj, c_obj.ob_type.tp_name, size)
    if c_obj.ob_type.tp_traverse != NULL:
        c_obj.ob_type.tp_traverse(c_obj, _dump_reference, out)
    if PyString_Check(c_obj):
        _dump_string(out, c_obj)
    elif PyUnicode_Check(c_obj):
        _dump_unicode(out, c_obj)
    fprintf(out, "\n")
    if c_obj.ob_type.tp_traverse != NULL:
        c_obj.ob_type.tp_traverse(c_obj, _dump_if_no_traverse, out)


def dump_object_info(object fp, object obj):
    cdef FILE *out

    out = PyFile_AsFile(fp)
    if out == NULL:
        raise TypeError('not a file')
    _dump_object_info(out, <PyObject *>obj)
