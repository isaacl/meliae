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

cdef extern from "Python.h":
    struct _typeobject:
        char * tp_name
        Py_ssize_t tp_basicsize
        Py_ssize_t tp_itemsize
    struct _object:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type

    ctypedef struct PyVarObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t ob_size

    ctypedef struct PyListObject:
        Py_ssize_t ob_refcnt
        _typeobject *ob_type
        Py_ssize_t allocated

    ctypedef _object PyObject

    int PyList_Check(object)
    int PyString_CheckExact(object)


cdef Py_ssize_t _basic_object_size(PyObject *c_obj):
    return c_obj.ob_type.tp_basicsize


cdef Py_ssize_t _var_object_size(PyVarObject *c_obj):
    return (c_obj.ob_type.tp_basicsize +
            c_obj.ob_size * c_obj.ob_type.tp_itemsize)


cdef Py_ssize_t _size_of_list(PyListObject *c_obj):
    cdef Py_ssize_t size
    size = _basic_object_size(<PyObject *>c_obj)
    size += sizeof(PyObject*) * c_obj.allocated
    return size


def size_of(obj):
    """Compute the size of the object.

    This is the actual malloc() size for this object, so for dicts it is the
    size of the dict object, plus the size of the array of references, but
    *not* the size of each individual referenced object.

    :param obj: The object to measure
    :return: An integer of the number of bytes used by this object.
    """
    cdef PyObject *c_obj

    if PyList_Check(obj):
        return _size_of_list(<PyListObject *>obj)

    c_obj = <PyObject *>obj
    if c_obj.ob_type.tp_itemsize != 0:
        # Variable length object with inline storage
        # total size is tp_itemsize * ob_size
        return _var_object_size(<PyVarObject *>c_obj)
    return _basic_object_size(c_obj)
