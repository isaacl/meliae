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
    void *realloc(void *, size_t)
    void *malloc(size_t)
    void free(void *)


cdef object _ref_list_to_list(long *ref_list):
    """Convert the notation of [len, items, ...] into [items].

    :param ref_list: A pointer to NULL, or to a list of longs. The list should
        start with the count of items
    """
    cdef long i
    # TODO: Always return a tuple, we already know the width, and this prevents
    #       double malloc()

    if ref_list == NULL:
        return ()
    refs = []
    for i from 1 <= i <= ref_list[0]:
        refs.append(ref_list[i])
    return refs


cdef long *_list_to_ref_list(object refs):
    cdef long i, num_refs, *ref_list

    num_refs = len(refs)
    if num_refs == 0:
        return NULL
    ref_list = <long*>malloc(sizeof(long)*(num_refs+1))
    ref_list[0] = num_refs
    i = 1
    for ref in refs:
        ref_list[i] = ref
        i = i + 1
    return ref_list


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
                         # If not null, the first item is the length of the
                         # list
    cdef readonly int length # Object length (ob_size), aka len(object)
    cdef public object value    # May be None, a PyString or a PyInt
    cdef readonly object name     # Name of this object (only valid for
                                  # modules, etc)
    cdef long *_referrer_list # An array of addresses that refer to this,
                              # if not null, the first item indicates the
                              # length of the list

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
            if self._ref_list != NULL:
                free(self._ref_list)
                self._ref_list = NULL
            self._ref_list = _list_to_ref_list(value)

    property num_refs:
        """The length of the ref_list."""
        def __get__(self):
            if self._ref_list == NULL:
                return 0
            return self._ref_list[0]

    property referrers:
        """The list of objects that reference this object.

        Original set to None, can be computed on demand.
        """
        def __get__(self):
            return _ref_list_to_list(self._referrer_list)

        def __set__(self, value):
            if self._referrer_list != NULL:
                free(self._referrer_list)
                self._referrer_list = NULL
            self._referrer_list = _list_to_ref_list(value)

    property num_referrers:
        """The length of the referrers list."""
        def __get__(self):
            if self._referrer_list == NULL:
                return 0
            return self._referrer_list[0]

    def __dealloc__(self):
        if self._ref_list != NULL:
            free(self._ref_list)
            self._ref_list = NULL
        if self._referrer_list != NULL:
            free(self._referrer_list)
            self._referrer_list = NULL

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
