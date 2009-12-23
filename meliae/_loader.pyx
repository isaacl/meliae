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

"""Routines and objects for loading dump files."""

cdef extern from "Python.h":
    ctypedef unsigned long size_t
    ctypedef struct PyObject:
        pass
    void *PyMem_Malloc(size_t)
    void PyMem_Free(void *)

    PyObject *PyDict_GetItem(object d, object key)
    int PyDict_SetItem(object d, object key, object val) except -1
    void Py_INCREF(PyObject*)
    void Py_DECREF(PyObject*)
    object PyTuple_New(Py_ssize_t)
    object PyTuple_SET_ITEM(object, Py_ssize_t, object)


ctypedef struct RefList:
    long size
    PyObject *refs[0]


cdef object _set_default(object d, object val):
    """Either return the value in the dict, or return 'val'.

    This is the same as Dict.setdefault, but without the attribute lookups. (It
    may be slightly worse because it does 2 dict lookups?)
    """
    cdef PyObject *tmp
    
    tmp = PyDict_GetItem(d, val)
    if tmp == NULL:
        PyDict_SetItem(d, val, val)
    else:
        val = <object>tmp
    return val


cdef _free_ref_list(RefList *ref_list):
    """Decref and free the list."""
    cdef long i

    if ref_list == NULL:
        return
    for i from 0 <= i < ref_list.size:
        Py_DECREF(ref_list.refs[i])
    PyMem_Free(ref_list)


cdef object _ref_list_to_list(RefList *ref_list):
    """Convert the notation of [len, items, ...] into [items].

    :param ref_list: A pointer to NULL, or to a list of longs. The list should
        start with the count of items
    """
    cdef long i
    # TODO: Always return a tuple, we already know the width, and this prevents
    #       double malloc(). However, this probably isn't a critical code path

    if ref_list == NULL:
        return ()
    refs = []
    for i from 0 <= i < ref_list.size:
        refs.append(<object>(ref_list.refs[i]))
    return refs


cdef RefList *_list_to_ref_list(object refs) except? NULL:
    cdef long i, num_refs
    cdef RefList *ref_list

    num_refs = len(refs)
    if num_refs == 0:
        return NULL
    ref_list = <RefList *>PyMem_Malloc(sizeof(RefList) +
                                       sizeof(PyObject*)*num_refs)
    ref_list.size = num_refs
    i = 0
    for ref in refs:
        ref_list.refs[i] = <PyObject*>ref
        Py_INCREF(ref_list.refs[i])
        i = i + 1
    return ref_list


cdef object _format_list(RefList *ref_list):
    cdef long i, max_refs

    if ref_list == NULL:
        return ''
    max_refs = ref_list.size
    if max_refs > 10:
        max_refs = 10
    ref_str = ['[']
    for i from 0 <= i < max_refs:
        if i == 0:
            ref_str.append('%d' % (<object>ref_list.refs[i]))
        else:
            ref_str.append(', %d' % (<object>ref_list.refs[i]))
    if ref_list.size > 10:
        ref_str.append(', ...]')
    else:
        ref_str.append(']')
    return ''.join(ref_str)


cdef class MemObject:
    """This defines the information we know about the objects.

    We use a Pyrex class, since in python each object is 40 bytes, but you also
    have to include the size of all the objects referenced. (a 4-byte integer,
    becomes a 12-byte PyInt.)

    :ivar address: The address in memory of the original object. This is used
        as the 'handle' to this object.
    :ivar type_str: The type of this object
    :ivar size: The number of bytes consumed for just this object. So for a
        dict, this would be the basic_size + the size of the allocated array to
        store the reference pointers
    :ivar ref_list: A list of items referenced from this object
    :ivar num_refs: Count of references
    :ivar value: A PyObject representing the Value for this object. (For
        strings, it is the first 100 bytes, it may be None if we have no value,
        or it may be an integer, etc.)
    :ivar name: Some objects have associated names, like modules, classes, etc.
    """

    cdef readonly object address  # We track the address by pointing to a PyInt
                                  # This is valid, because we put these objects
                                  # into a dict anyway, so we need a PyInt
                                  # And we can just share it
    cdef readonly object type_str # pointer to a PyString, this is expected to
                                  # be shared with many other instances, but
                                  # longer than 4 bytes
    cdef public long size # Number of bytes consumed by this instance
    # TODO: Right now this points to the integer offset, which we then look up
    #       in the OM dict. However, if we are going to go with PyObject *, why
    #       not just point to the final object anyway...
    cdef RefList *_ref_list # An array of addresses that this object
                            # referenced. May be NULL if len() == 0
    cdef readonly int length # Object length (ob_size), aka len(object)
    cdef public object value    # May be None, a PyString or a PyInt
    cdef readonly object name     # Name of this object (only valid for
                                  # modules, etc)
    cdef RefList *_referrer_list # An array of addresses that refer to this,

    cdef public unsigned long total_size # Size of everything referenced from
                                         # this object

    def __init__(self, address, type_str, size, ref_list, length=None,
                 value=None, name=None):
        self.address = address
        self.type_str = type_str
        self.size = size
        self._ref_list = _list_to_ref_list(ref_list)
        if length is None:
            self.length = -1
        else:
            self.length = length
        self.value = value
        self.name = name
        self._referrer_list = NULL
        self.total_size = 0 # uncomputed yet

    property ref_list:
        """The list of objects referenced by this object."""
        def __get__(self):
            return _ref_list_to_list(self._ref_list)

        def __set__(self, value):
            _free_ref_list(self._ref_list)
            self._ref_list = _list_to_ref_list(value)

    property num_refs:
        """The length of the ref_list."""
        def __get__(self):
            if self._ref_list == NULL:
                return 0
            return self._ref_list.size

    property referrers:
        """The list of objects that reference this object.

        Original set to None, can be computed on demand.
        """
        def __get__(self):
            return _ref_list_to_list(self._referrer_list)

        def __set__(self, value):
            _free_ref_list(self._referrer_list)
            self._referrer_list = _list_to_ref_list(value)

    property num_referrers:
        """The length of the referrers list."""
        def __get__(self):
            if self._referrer_list == NULL:
                return 0
            return self._referrer_list.size

    def __dealloc__(self):
        cdef long i
        _free_ref_list(self._ref_list)
        self._ref_list = NULL
        _free_ref_list(self._referrer_list)
        self._referrer_list = NULL

    def __repr__(self):
        cdef int i, max_refs
        cdef double total_size
        if self.name is not None:
            name_str = ', %s' % (self.name,)
        else:
            name_str = ''
        if self._ref_list == NULL:
            num_refs = 0
            ref_space = ''
            ref_str = ''
        else:
            num_refs = self._ref_list.size
            ref_str = _format_list(self._ref_list)
            ref_space = ' '
        if self._referrer_list == NULL:
            referrer_str = ''
        else:
            referrer_str = ', %d referrers %s' % (
                self._referrer_list.size,
                _format_list(self._referrer_list))
        if self.value is None:
            value_str = ''
        else:
            r = repr(self.value)
            if isinstance(self.value, basestring):
                if len(r) > 21:
                    r = r[:18] + "..."
            value_str = ', %s' % (r,)
        if self.total_size == 0:
            total_size_str = ''
        else:
            total_size = self.total_size
            order = 'B'
            if total_size > 800.0:
                total_size = total_size / 1024
                order = 'KiB'
            if total_size > 800.0:
                total_size = total_size / 1024
                order = 'MiB'
            if total_size > 800.0:
                total_size = total_size / 1024
                order = 'GiB'
            total_size_str = ', %.1f%s' % (total_size, order)
            

        return ('%s(%d, %s%s, %d bytes, %d refs%s%s%s%s%s)'
                % (self.__class__.__name__, self.address, self.type_str,
                   name_str, self.size, num_refs, ref_space, ref_str,
                   referrer_str, value_str, total_size_str))

    def __getitem__(self, offset):
        cdef long off
        cdef PyObject *res

        if self._ref_list == NULL:
            raise IndexError('%s has no refs' % (self,))
        off = offset
        if off >= self._ref_list.size:
            raise IndexError('%s has only %d refs'
                             % (self, self._ref_list.size))
        res = self._ref_list.refs[off]
        return <object>res

    def _intern_from_cache(self, cache):
        self.address = _set_default(cache, self.address)
        self.type_str = _set_default(cache, self.type_str)

    def to_json(self):
        """Convert this MemObject to json."""
        refs = []
        for ref in sorted(self.ref_list):
            refs.append(str(ref))
        if self.length != -1:
            length = '"len": %d, ' % self.length
        else:
            length = ''
        if self.value is not None:
            if self.type_str == 'int':
                value = '"value": %s, ' % self.value
            else:
                value = '"value": "%s", ' % self.value
        else:
            value = ''
        if self.name:
            name = '"name": "%s", ' % self.name
        else:
            name = ''
        return '{"address": %d, "type": "%s", "size": %d, %s%s%s"refs": [%s]}' % (
            self.address, self.type_str, self.size, name, length, value,
            ', '.join(refs))
