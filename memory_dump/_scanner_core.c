/* Copyright (C) 2009 Canonical Ltd
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
 */

/* The core of parsing is split into a pure C module, so that we can guarantee
 * that we won't be creating objects in the internal loops.
 */

#include "_scanner_core.h"

Py_ssize_t
_basic_object_size(PyObject *c_obj)
{
    return c_obj->ob_type->tp_basicsize;
}


Py_ssize_t
_var_object_size(PyVarObject *c_obj)
{
    return (c_obj->ob_type->tp_basicsize +
            c_obj->ob_size * c_obj->ob_type->tp_itemsize);
}


Py_ssize_t
_size_of_list(PyListObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    size += sizeof(PyObject*) * c_obj->allocated;
    return size;
}


Py_ssize_t
_size_of_set(PySetObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    if (c_obj->table != c_obj->smalltable) {
        size += sizeof(setentry) * (c_obj->mask + 1);
    }
    return size;
}


Py_ssize_t
_size_of_dict(PyDictObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    if (c_obj->ma_table != c_obj->ma_smalltable) {
        size += sizeof(PyDictEntry) * (c_obj->ma_mask + 1);
    }
    return size;
}


Py_ssize_t
_size_of_unicode(PyUnicodeObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    size += Py_UNICODE_SIZE * c_obj->length;
    return size;
}


Py_ssize_t
_size_of(PyObject *c_obj)
{
    if PyList_Check(c_obj) {
        return _size_of_list((PyListObject *)c_obj);
    } else if PyAnySet_Check(c_obj) {
        return _size_of_set((PySetObject *)c_obj);
    } else if PyDict_Check(c_obj) {
        return _size_of_dict((PyDictObject *)c_obj);
    } else if PyUnicode_Check(c_obj) {
        return _size_of_unicode((PyUnicodeObject *)c_obj);
    } 

    if (c_obj->ob_type->tp_itemsize != 0) {
        // Variable length object with inline storage
        // total size is tp_itemsize * ob_size
        return _var_object_size((PyVarObject *)c_obj);
    }
    return _basic_object_size(c_obj);
}

// cdef int _dump_reference(PyObject *c_obj, void* val):
//     cdef FILE *out
//     out = <FILE *>val
//     fprintf(out, " 0x%08lx", <long>c_obj)
//     return 0
// 
// 
// cdef void _dump_string(FILE *out, PyObject *c_obj):
//     # TODO: consider writing to a small memory buffer, before writing to disk
//     cdef Py_ssize_t str_size
//     cdef char *str_buf
//     cdef Py_ssize_t i
// 
//     str_buf = PyString_AS_STRING(c_obj)
//     str_size = PyString_GET_SIZE(c_obj)
// 
//     # Never try to dump more than this many chars
//     if str_size > 100:
//         str_size = 100
//     fprintf(out, " s ")
//     for i from 0 <= i < str_size:
//         fprintf(out, "%02x", <int>str_buf[i])
// 
// 
// cdef void _dump_unicode(FILE *out, PyObject *c_obj):
//     # TODO: consider writing to a small memory buffer, before writing to disk
//     cdef Py_ssize_t uni_size
//     cdef Py_UNICODE *uni_buf
//     cdef Py_ssize_t i
// 
//     uni_buf = PyUnicode_AS_UNICODE(c_obj)
//     uni_size = PyUnicode_GET_SIZE(c_obj)
// 
//     # Never try to dump more than this many chars
//     if uni_size > 100:
//         uni_size = 100
//     fprintf(out, " u ")
//     for i from 0 <= i < uni_size:
//         fprintf(out, "%08x", <unsigned int>uni_buf[i])
// 
// 
// cdef int _dump_if_no_traverse(PyObject *c_obj, void* val):
//     cdef FILE *out
//     if c_obj.ob_type.tp_traverse != NULL:
//         return 0
//     out = <FILE *>val
//     # We know that it is safe to recurse here, because tp_traverse is NULL
//     _dump_object_info(out, c_obj)
//     return 0
// 
// 
// cdef void _dump_object_info(FILE *out, PyObject * c_obj):
//     cdef Py_ssize_t size
// 
//     size = _size_of(c_obj)
//     fprintf(out, "0x%08lx %s %d", <long>c_obj, c_obj.ob_type.tp_name, size)
//     if c_obj.ob_type.tp_traverse != NULL:
//         c_obj.ob_type.tp_traverse(c_obj, _dump_reference, out)
//     if PyString_Check(c_obj):
//         _dump_string(out, c_obj)
//     elif PyUnicode_Check(c_obj):
//         _dump_unicode(out, c_obj)
//     fprintf(out, "\n")
//     if c_obj.ob_type.tp_traverse != NULL:
//         c_obj.ob_type.tp_traverse(c_obj, _dump_if_no_traverse, out)
// 
// 
// def dump_object_info(object fp, object obj):
//     cdef FILE *out
// 
//     out = PyFile_AsFile(fp)
//     if out == NULL:
//         raise TypeError('not a file')
//     _dump_object_info(out, <PyObject *>obj)
