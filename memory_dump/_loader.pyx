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

"""Routines and objects for loading dump files."""

cdef extern from "Python.h":
    ctypedef unsigned long size_t
    ctypedef struct PyObject:
        pass
    void *malloc(size_t)
    void free(void *)


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

    cdef readonly long address
    cdef readonly object type_str # pointer to a PyString, this is expected to be shared
                                  # with many other instances, but longer than 4 bytes
    cdef readonly long size
    cdef long *_ref_list # An array of addresses that this object
                         # referenced. May be NULL if len() == 0
    cdef Py_ssize_t num_refs # Length of ref_list
    cdef readonly int length # Object length (ob_size), aka len(object)
    cdef public object value    # May be None, a PyString or a PyInt
    cdef readonly object name     # Name of this object (only valid for
                                  # modules, etc)

    def __init__(self, address, type_str, size, ref_list, length=None,
                 value=None, name=None):
        cdef int i
        self.address = address
        self.type_str = type_str
        self.size = size
        self.num_refs = len(ref_list)
        if self.num_refs == 0:
            self._ref_list = NULL
        else:
            self._ref_list = <long*>malloc(sizeof(long)*self.num_refs)
            i = 0
            for ref in ref_list:
                self._ref_list[i] = ref
                i = i + 1
        if length is None:
            self.length = -1
        else:
            self.length = length
        self.value = value
        self.name = name

    property ref_list:
        """The list of objects referenced by this object."""
        def __get__(self):
            cdef int i
            refs = []
            for i from 0 <= i < self.num_refs:
                refs.append(self._ref_list[i])
            return refs

    def __dealloc__(self):
        if self._ref_list != NULL:
            free(self._ref_list)
            self._ref_list = NULL

    def __repr__(self):
        if self.name is not None:
            name_str = ', %s' % (self.name,)
        else:
            name_str = ''
        return ('%s(%08x, %s%s, %d bytes, %d refs)'
                % (self.__class__.__name__, self.address, self.type_str,
                   name_str, self.size, len(self.ref_list)))

    def _intern_from_cache(self, cache):
        self.type_str = cache.setdefault(self.type_str, self.type_str)
