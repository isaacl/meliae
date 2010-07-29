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

"""Routines and objects for loading dump files."""

cdef extern from "Python.h":
    ctypedef unsigned long size_t
    ctypedef struct PyObject:
        pass
    PyObject *Py_None
    void *PyMem_Malloc(size_t)
    void PyMem_Free(void *)

    long PyObject_Hash(PyObject *) except -1

    object PyList_New(Py_ssize_t)
    void PyList_SET_ITEM(object, Py_ssize_t, object)
    PyObject *PyDict_GetItem(object d, object key)
    PyObject *PyDict_GetItem_ptr "PyDict_GetItem" (object d, PyObject *key)
    int PyDict_SetItem(object d, object key, object val) except -1
    int PyDict_SetItem_ptr "PyDict_SetItem" (object d, PyObject *key,
                                             PyObject *val) except -1
    void Py_INCREF(PyObject*)
    void Py_XDECREF(PyObject*)
    void Py_DECREF(PyObject*)
    object PyTuple_New(Py_ssize_t)
    object PyTuple_SET_ITEM(object, Py_ssize_t, object)
    int PyObject_RichCompareBool(PyObject *, PyObject *, int) except -1
    int Py_EQ
    void memset(void *, int, size_t)

    # void fprintf(void *, char *, ...)
    # void *stderr

import gc
from meliae import warn


ctypedef struct RefList:
    long size
    PyObject *refs[0]


cdef Py_ssize_t sizeof_RefList(RefList *val):
    """Determine how many bytes for this ref list. val() can be NULL"""
    if val == NULL:
        return 0
    return sizeof(long) + (sizeof(PyObject *) * val.size)


cdef object _set_default(object d, object val):
    """Either return the value in the dict, or return 'val'.

    This is the same as Dict.setdefault, but without the attribute lookups. (It
    may be slightly worse because it does 2 dict lookups?)
    """
    cdef PyObject *tmp

    # TODO: Note that using _lookup directly would remove the need to ever do a
    #       double-lookup to set the value
    tmp = PyDict_GetItem(d, val)
    if tmp == NULL:
        PyDict_SetItem(d, val, val)
    else:
        val = <object>tmp
    return val


cdef int _set_default_ptr(object d, PyObject **val) except -1:
    """Similar to _set_default, only it sets the val in place"""
    cdef PyObject *tmp

    tmp = PyDict_GetItem_ptr(d, val[0])
    if tmp == NULL:
        # val is unchanged, so we don't change the refcounts
        PyDict_SetItem_ptr(d, val[0], val[0])
        return 0
    else:
        # We will be pointing val to something new, so fix up the refcounts
        Py_INCREF(tmp)
        Py_DECREF(val[0])
        val[0] = tmp
        return 1


cdef int _free_ref_list(RefList *ref_list) except -1:
    """Decref and free the list."""
    cdef long i

    if ref_list == NULL:
        return 0
    for i from 0 <= i < ref_list.size:
        if ref_list.refs[i] == NULL:
            raise RuntimeError('Somehow we got a NULL reference.')
        Py_DECREF(ref_list.refs[i])
    PyMem_Free(ref_list)
    return 1


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
    refs_append = refs.append
    for i from 0 <= i < ref_list.size:
        refs_append(<object>(ref_list.refs[i]))
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


cdef struct _MemObject:
    # """The raw C structure, used to minimize memory allocation size."""
    PyObject *address
    PyObject *type_str
    # Consider making this unsigned long
    long size
    RefList *child_list
    # Removed for now, since it hasn't proven useful
    # int length
    PyObject *value
    # TODO: I don't think I've found an object that has both a value and a
    #       name. As such, I should probably remove the redundancy, as it saves
    #       a pointer
    # PyObject *name
    RefList *parent_list
    unsigned long total_size
    # This is an uncounted ref to a _MemObjectProxy. _MemObjectProxy also has a
    # refreence to this object, so when it disappears it can set the reference
    # to NULL.
    PyObject *proxy


cdef _MemObject *_new_mem_object(address, type_str, size, children,
                             value, name, parent_list, total_size) except NULL:
    cdef _MemObject *new_entry
    cdef PyObject *addr

    new_entry = <_MemObject *>PyMem_Malloc(sizeof(_MemObject))
    if new_entry == NULL:
        raise MemoryError('Failed to allocate %d bytes' % (sizeof(_MemObject),))
    memset(new_entry, 0, sizeof(_MemObject))
    addr = <PyObject *>address
    Py_INCREF(addr)
    new_entry.address = addr
    new_entry.type_str = <PyObject *>type_str
    Py_INCREF(new_entry.type_str)
    new_entry.size = size
    new_entry.child_list = _list_to_ref_list(children)
    # TODO: Was found wanting and removed
    # if length is None:
    #     new_entry.length = -1
    # else:
    #     new_entry.length = length
    if value is not None and name is not None:
        raise RuntimeError("We currently only support one of value or name"
                           " per object.")
    if value is not None:
        new_entry.value = <PyObject *>value
    else:
        new_entry.value = <PyObject *>name
    Py_INCREF(new_entry.value)
    new_entry.parent_list = _list_to_ref_list(parent_list)
    new_entry.total_size = total_size
    return new_entry


cdef int _free_mem_object(_MemObject *cur) except -1:
    if cur == NULL: # Already cleared
        return 0
    if cur == _dummy:
        return 0
    if cur.address == NULL:
        raise RuntimeError('clering something that doesn\'t have address')
    Py_XDECREF(cur.address)
    cur.address = NULL
    Py_XDECREF(cur.type_str)
    cur.type_str = NULL
    _free_ref_list(cur.child_list)
    cur.child_list = NULL
    Py_XDECREF(cur.value)
    cur.value = NULL
    # Py_XDECREF(cur.name)
    # cur.name = NULL
    _free_ref_list(cur.parent_list)
    cur.parent_list = NULL
    cur.proxy = NULL
    PyMem_Free(cur)
    return 1


cdef _MemObject *_dummy
_dummy = <_MemObject*>(-1)


cdef class MemObjectCollection
cdef class _MemObjectProxy


def _MemObjectProxy_from_args(address, type_str, size, children=(), length=0,
                              value=None, name=None, parent_list=(),
                              total_size=0):
    """Create a standalone _MemObjectProxy instance.

    Note that things like '__getitem__' won't work, as they query the
    collection for the actual data.
    """
    cdef _MemObject *new_entry
    cdef _MemObjectProxy proxy

    new_entry = _new_mem_object(address, type_str, size, children,
                                value, name, parent_list, total_size)
    proxy = _MemObjectProxy(None)
    proxy._obj = new_entry
    proxy._managed_obj = new_entry
    new_entry.proxy = <PyObject *>proxy
    return proxy


cdef class _MemObjectProxy:
    """The standard interface for understanding memory consumption.

    MemObjectCollection stores the data as a fairly efficient table, without
    the overhead of having a regular python object for every data point.
    However, the rest of python code needs to interact with a real python
    object, so we generate these on-the-fly.

    Most attributes are properties, which thunk over to the actual data table
    entry.

    :ivar address: The address in memory of the original object. This is used
        as the 'handle' to this object.
    :ivar type_str: The type of this object
    :ivar size: The number of bytes consumed for just this object. So for a
        dict, this would be the basic_size + the size of the allocated array to
        store the reference pointers
    :ivar children: A list of items referenced from this object
    :ivar num_refs: Count of references, you can also use len()
    :ivar value: A PyObject representing the Value for this object. (For
        strings, it is the first 100 bytes, it may be None if we have no value,
        or it may be an integer, etc.) This is also where the 'name' is stored
        for objects like 'module'.
    :ivar
    """

    cdef MemObjectCollection collection
    # This must be set immediately after construction, before accessing any
    # member vars
    cdef _MemObject *_obj
    # If not NULL, this will be freed when this object is deallocated
    cdef _MemObject *_managed_obj

    def __init__(self, collection):
        self.collection = collection
        self._obj = NULL
        self._managed_obj = NULL

    def __dealloc__(self):
        if self._obj != NULL:
            if self._obj.proxy == <PyObject *>self:
                # This object is going away, remove the reference
                self._obj.proxy = NULL
            # else:
            #     fprintf(stderr, "obj at address %x referenced"
            #         " a proxy that was not self\n",
            #         <int><object>self._obj.address)
        if self._managed_obj != NULL:
            _free_mem_object(self._managed_obj)
            self._managed_obj = NULL

    def __sizeof__(self):
        my_size = sizeof(_MemObjectProxy)
        if self._managed_obj != NULL:
            my_size += sizeof(_MemObject)
        # XXX: Note that to get the memory dump correct for all this stuff,
        #      We need to walk all the RefList objects and get their size, and
        #      tp_traverse should be walking to all of those referenced
        #      integers, etc.
        return my_size

    property address:
        """The identifier for the tracked object."""
        def __get__(self):
            return <object>(self._obj.address)

    property type_str:
        """The type of this object."""
        def __get__(self):
            return <object>(self._obj.type_str)

        def __set__(self, value):
            cdef PyObject *ptr
            ptr = <PyObject *>value
            Py_INCREF(ptr)
            Py_DECREF(self._obj.type_str)
            self._obj.type_str = ptr

    property size:
        """The number of bytes allocated for this object."""
        def __get__(self):
            return self._obj.size

        def __set__(self, value):
            self._obj.size = value

    # property name:
    #     """Name associated with this object."""
    #     def __get__(self):
    #         return <object>self._obj.name

    property value:
        """Value for this object (for strings and ints)"""
        def __get__(self):
            return <object>self._obj.value

        def __set__(self, value):
            cdef PyObject *new_val
            new_val = <PyObject *>value
            # INCREF first, just in case value is self._obj.value
            Py_INCREF(new_val)
            Py_DECREF(self._obj.value)
            self._obj.value = new_val

    property total_size:
        """Mean to hold the size of this plus size of all referenced objects."""
        def __get__(self):
            return self._obj.total_size

        def __set__(self, value):
            self._obj.total_size = value

    def __len__(self):
        if self._obj.child_list == NULL:
            return 0
        return self._obj.child_list.size

    property num_refs:
        def __get__(self):
            warn.deprecated('Attribute .num_refs deprecated.'
                            ' Use len() instead.')
            return self.__len__()

    def _intern_from_cache(self, cache):
        cdef long i
        _set_default_ptr(cache, &self._obj.address)
        _set_default_ptr(cache, &self._obj.type_str)
        if self._obj.child_list != NULL:
            for i from 0 <= i < self._obj.child_list.size:
                _set_default_ptr(cache, &self._obj.child_list.refs[i])
        if self._obj.parent_list != NULL:
            for i from 0 <= i < self._obj.parent_list.size:
                _set_default_ptr(cache, &self._obj.parent_list.refs[i])


    property children:
        """The list of objects referenced by this object."""
        def __get__(self):
            return _ref_list_to_list(self._obj.child_list)

        def __set__(self, value):
            _free_ref_list(self._obj.child_list)
            self._obj.child_list = _list_to_ref_list(value)

    property ref_list:
        """The list of objects referenced by this object.

        Deprecated, use .children instead.
        """
        def __get__(self):
            warn.deprecated('Attribute .ref_list deprecated.'
                            ' Use .children instead.')
            return self.children

        def __set__(self, val):
            warn.deprecated('Attribute .ref_list deprecated.'
                            ' Use .children instead.')
            self.children = val

    property referrers:
        """Objects which refer to this object.

        Deprecated, use .parents instead.
        """
        def __get__(self):
            warn.deprecated('Attribute .referrers deprecated.'
                            ' Use .parents instead.')
            return self.parents

        def __set__(self, value):
            warn.deprecated('Attribute .referrers deprecated.'
                            ' Use .parents instead.')
            self.parents = value

    property parents:
        """The list of objects that reference this object.

        Original set to None, can be computed on demand.
        """
        def __get__(self):
            return _ref_list_to_list(self._obj.parent_list)

        def __set__(self, value):
            _free_ref_list(self._obj.parent_list)
            self._obj.parent_list = _list_to_ref_list(value)

    property num_referrers:
        """The length of the parents list."""
        def __get__(self):
            warn.deprecated('Attribute .num_referrers deprecated.'
                            ' Use .num_parents instead.')
            if self._obj.parent_list == NULL:
                return 0
            return self._obj.parent_list.size

    property num_parents:
        """The length of the parents list."""
        def __get__(self):
            if self._obj.parent_list == NULL:
                return 0
            return self._obj.parent_list.size

    def __getitem__(self, offset):
        cdef long off

        if self._obj.child_list == NULL:
            raise IndexError('%s has no references' % (self,))
        off = offset
        if off >= self._obj.child_list.size:
            raise IndexError('%s has only %d (not %d) references'
                             % (self, self._obj.child_list.size, offset))
        address = <object>self._obj.child_list.refs[off]
        try:
            return self.collection[address]
        except KeyError:
            # TODO: What to do if the object isn't present? I think returning a
            #       'no-such-object' proxy would be nicer than returning nothing
            raise

    property c:
        """The list of children objects as objects (not references)."""
        def __get__(self):
            cdef long pos

            result = []
            if self._obj.child_list == NULL:
                return result
            for pos from 0 <= pos < self._obj.child_list.size:
                address = <object>self._obj.child_list.refs[pos]
                obj = self.collection[address]
                result.append(obj)
            return result

    property p:
        """The list of parent objects as objects (not references)."""
        def __get__(self):
            cdef long pos

            result = []
            if self._obj.parent_list == NULL:
                return result
            for pos from 0 <= pos < self._obj.parent_list.size:
                address = <object>self._obj.parent_list.refs[pos]
                try:
                    obj = self.collection[address]
                except KeyError:
                    # We should probably create an "unknown object" type
                    raise
                result.append(obj)
            return result

    def __repr__(self):
        if self._obj.child_list == NULL:
            refs = ''
        else:
            refs = ' %drefs' % (self._obj.child_list.size,)
        if self._obj.parent_list == NULL:
            parent_str = ''
        else:
            parent_str = ' %dpar' % (self._obj.parent_list.size,)
        if self._obj.value == NULL or self._obj.value == Py_None:
            val = ''
        else:
            val = ' %r' % (<object>self._obj.value,)
        if self._obj.total_size == 0:
            total_size_str = ''
        else:
            total_size = float(self._obj.total_size)
            order = 'B'
            if total_size > 800.0:
                total_size = total_size / 1024.0
                order = 'K'
            if total_size > 800.0:
                total_size = total_size / 1024.0
                order = 'M'
            if total_size > 800.0:
                total_size = total_size / 1024.0
                order = 'G'
            total_size_str = ' %.1f%stot' % (total_size, order)
        return '%s(%d %dB%s%s%s%s)' % (
            self.type_str, self.address, self.size,
            refs, parent_str, val, total_size_str)

    def to_json(self):
        """Convert this back into json."""
        refs = []
        for ref in sorted(self.children):
            refs.append(str(ref))
        # Note: We've lost the info about whether this was a value or a name
        #       We've also lost the 'length' field.
        if self.value is not None:
            if self.type_str == 'int':
                value = '"value": %s, ' % self.value
            else:
                # TODO: This isn't perfect, as it doesn't do proper json
                #       escaping
                value = '"value": "%s", ' % self.value
        else:
            value = ''
        return '{"address": %d, "type": "%s", "size": %d, %s"refs": [%s]}' % (
            self.address, self.type_str, self.size, value, ', '.join(refs))

    def refs_as_dict(self):
        """Expand the ref list considering it to be a 'dict' structure.

        Often we have dicts that point to simple strings and ints, etc. This
        tries to expand that as much as possible.
        """
        as_dict = {}
        children = self.children
        if len(children) % 2 == 1 and self.type_str not in ('dict', 'module'):
            # Instance dicts end with a 'type' reference, but only do that if
            # we actually have an odd number
            children = children[:-1]
        for idx in xrange(0, len(children), 2):
            key = self.collection[children[idx]]
            val = self.collection[children[idx+1]]
            if key.value is not None:
                key = key.value
            # TODO: We should consider recursing if val is a 'known' type, such
            #       a tuple/dict/etc
            if val.type_str == 'bool':
                val = (val.value == 'True')
            elif val.type_str in ('int', 'long', 'str', 'unicode', 'float',
                                  ) and val.value is not None:
                val = val.value
            elif val.type_str == 'NoneType':
                val = None
            as_dict[key] = val
        return as_dict

    def iter_recursive_refs(self, excluding=None):
        """Find all objects referenced from this one (including self).

        Self will always be the first object returned, in case you want to
        exclude it (though it can be excluded in the excluding list). This is
        done because it is cumbersome to add it back in, but easy to exclude.

        :param excluding: This can be any iterable of addresses. We will not
            walk to anything in this list (including self).
        :return: Iterator over all objects that can be reached.
        """
        cdef _MOPReferencedIterator iterator
        iterator = _MOPReferencedIterator(self, excluding)
        return iterator



cdef class MemObjectCollection:
    """Track a bunch of _MemObject instances."""

    cdef readonly int _table_mask  # N slots = table_mask + 1
    cdef readonly int _active      # How many slots have real data
    cdef readonly int _filled      # How many slots have real or dummy
    cdef _MemObject** _table       # _MemObjects are stored inline

    def __init__(self):
        self._table_mask = 1024 - 1
        self._table = <_MemObject**>PyMem_Malloc(sizeof(_MemObject*)*1024)
        memset(self._table, 0, sizeof(_MemObject*)*1024)

    def __len__(self):
        return self._active

    def __sizeof__(self):
        cdef int i
        cdef _MemObject *cur
        cdef long my_size
        my_size = (sizeof(MemObjectCollection)
            + (sizeof(_MemObject**) * (self._table_mask + 1)))
        for i from 0 <= i <= self._table_mask:
            cur = self._table[i]
            if cur != NULL and cur != _dummy:
                my_size += (sizeof_RefList(cur.child_list)
                            + sizeof_RefList(cur.parent_list))
        return my_size

    cdef _MemObject** _lookup(self, address) except NULL:
        cdef long the_hash
        cdef size_t i, n_lookup
        cdef long mask
        cdef _MemObject **table, **slot, **free_slot
        cdef PyObject *py_addr

        py_addr = <PyObject *>address
        the_hash = PyObject_Hash(py_addr)
        i = <size_t>the_hash
        mask = self._table_mask
        table = self._table
        free_slot = NULL
        for n_lookup from 0 <= n_lookup <= <size_t>mask: # Don't loop forever
            slot = &table[i & mask]
            if slot[0] == NULL:
                # Found a blank spot
                if free_slot != NULL:
                    # Did we find an earlier _dummy entry?
                    return free_slot
                else:
                    return slot
            elif slot[0] == _dummy:
                if free_slot == NULL:
                    free_slot = slot
            elif slot[0].address == py_addr:
                # Found an exact pointer to the key
                return slot
            elif slot[0].address == NULL:
                raise RuntimeError('Found a non-empty slot with null address')
            elif PyObject_RichCompareBool(slot[0].address, py_addr, Py_EQ):
                # Both py_key and cur belong in this slot, return it
                return slot
            i = i + 1 + n_lookup
        raise RuntimeError('we failed to find an open slot after %d lookups'
                           % (n_lookup))

    cdef int _clear_slot(self, _MemObject **slot) except -1:
        _free_mem_object(slot[0])
        slot[0] = NULL
        return 1

    def _test_lookup(self, address):
        cdef _MemObject **slot

        slot = self._lookup(address)
        return (slot - self._table)

    def __contains__(self, address):
        cdef _MemObject **slot

        slot = self._lookup(address)
        if slot[0] == NULL or slot[0] == _dummy:
            return False
        return True

    cdef _MemObjectProxy _proxy_for(self, address, _MemObject *val):
        cdef _MemObjectProxy proxy

        if val.proxy == NULL:
            proxy = _MemObjectProxy(self)
            proxy._obj = val
            val.proxy = <PyObject *>proxy
        else:
            proxy = <object>val.proxy
        return proxy

    def __getitem__(self, at):
        cdef _MemObject **slot
        cdef _MemObjectProxy proxy

        if isinstance(at, _MemObjectProxy):
            address = at.address
            proxy = at
        else:
            address = at
            proxy = None

        slot = self._lookup(address)
        if slot[0] == NULL or slot[0] == _dummy:
            raise KeyError('address %s not present' % (at,))
        if proxy is None:
            proxy = self._proxy_for(address, slot[0])
        else:
            assert proxy._obj == slot[0]
        return proxy

    def get(self, at, default=None):
        try:
            return self[at]
        except KeyError:
            return default

    def __delitem__(self, at):
        cdef _MemObject **slot
        cdef _MemObjectProxy proxy

        if isinstance(at, _MemObjectProxy):
            address = at.address
        else:
            address = at

        slot = self._lookup(address)
        if slot[0] == NULL or slot[0] == _dummy:
            raise KeyError('address %s not present' % (at,))
        if slot[0].proxy != NULL:
            # Have the proxy take over the memory lifetime. At the same time,
            # we break the reference cycle, so that the proxy will get cleaned
            # up properly
            proxy = <object>slot[0].proxy
            proxy._managed_obj = proxy._obj
        else:
            # Without a proxy, we just nuke the object
            self._clear_slot(slot)
        slot[0] = _dummy
        self._active -= 1
        # TODO: Shrink

    #def __setitem__(self, address, value):
    #    """moc[address] = value"""
    #    pass

    cdef int _insert_clean(self, _MemObject *entry) except -1:
        """Copy _MemObject into the table.

        We know that this _MemObject is unique, and we know that self._table
        contains no _dummy entries. So we can do the lookup cheaply, without
        any equality checks, etc.
        """
        cdef long the_hash
        cdef size_t i, n_lookup, mask
        cdef _MemObject **slot

        assert entry != NULL and entry.address != NULL
        mask = <size_t>self._table_mask
        the_hash = <size_t>PyObject_Hash(entry.address)
        i = <size_t>the_hash
        for n_lookup from 0 <= n_lookup < mask:
            slot = &self._table[i & mask]
            if slot[0] == NULL:
                slot[0] = entry
                self._filled += 1
                self._active += 1
                return 1
            i = i + 1 + n_lookup
        raise RuntimeError('could not find a free slot after %d lookups'
                           % (n_lookup,))

    cdef int _resize(self, int min_active) except -1:
        """Resize the internal table.

        We will be big enough to hold at least 'min_active' entries. We will
        create a copy of all data, leaving out dummy entries.

        :return: The new table size.
        """
        cdef int new_size, remaining
        cdef size_t n_bytes
        cdef _MemObject **old_table, **old_slot, **new_table

        new_size = 1024
        while new_size <= min_active and new_size > 0:
            new_size <<= 1
        if new_size <= 0:
            raise MemoryError('table size too large for %d entries'
                              % (min_active,))
        n_bytes = sizeof(_MemObject*)*new_size
        new_table = <_MemObject**>PyMem_Malloc(n_bytes)
        if new_table == NULL:
            raise MemoryError('Failed to allocate %d bytes' % (n_bytes,))
        memset(new_table, 0, n_bytes)
        old_slot = old_table = self._table
        self._table = new_table
        self._table_mask = new_size - 1
        remaining = self._active
        self._filled = 0
        self._active = 0

        while remaining > 0:
            if old_slot[0] == NULL:
                pass # empty
            elif old_slot[0] == _dummy:
                pass # dummy
            else:
                remaining -= 1
                self._insert_clean(old_slot[0])
            old_slot += 1
        # Moving everything over is refcount neutral, so we just free the old
        # table
        PyMem_Free(old_table)
        return new_size

    def add(self, address, type_str, size, children=(), length=0,
            value=None, name=None, parent_list=(), total_size=0):
        """Add a new MemObject to this collection."""
        cdef _MemObject **slot, *new_entry
        cdef _MemObjectProxy proxy

        slot = self._lookup(address)
        if slot[0] != NULL and slot[0] != _dummy:
            # We are overwriting an existing entry, for now, fail
            # Probably all we have to do is clear the slot first, then continue
            assert False, "We don't support overwrite yet."
        # TODO: These are fairy small and more subject to churn, maybe we
        #       should be using PyObj_Malloc instead...
        new_entry = _new_mem_object(address, type_str, size, children,
                                    value, name, parent_list, total_size)

        if slot[0] == NULL:
            self._filled += 1
        self._active += 1
        slot[0] = new_entry
        if self._filled * 3 > (self._table_mask + 1) * 2:
            # We need to grow
            self._resize(self._active * 2)
        proxy = self._proxy_for(address, new_entry)
        return proxy

    def __dealloc__(self):
        cdef long i

        for i from 0 <= i < self._table_mask:
            self._clear_slot(self._table + i)
        PyMem_Free(self._table)
        self._table = NULL

    def __iter__(self):
        return self.iterkeys()

    def iterkeys(self):
        return iter(self.keys())

    def keys(self):
        cdef long i
        cdef _MemObject *cur
        cdef _MemObjectProxy proxy

        # TODO: Pre-allocate the full size list
        values = []
        for i from 0 <= i < self._table_mask:
            cur = self._table[i]
            if cur == NULL or cur == _dummy:
                continue
            else:
                address = <object>cur.address
                values.append(address)
        return values

    def iteritems(self):
        return self.items()

    def items(self):
        """Iterate over (key, value) tuples."""
        cdef long i, out_idx
        cdef _MemObject *cur
        cdef _MemObjectProxy proxy

        enabled = gc.isenabled()
        if enabled:
            # We are going to be creating a lot of objects here, but not with
            # cycles, so we disable gc temporarily
            # With an object list of ~3M items, this drops the .items() time
            # from 25s down to 1.3s
            gc.disable()
        try:
            values = PyList_New(self._active)
            out_idx = 0
            for i from 0 <= i < self._table_mask:
                cur = self._table[i]
                if cur == NULL or cur == _dummy:
                    continue
                else:
                    address = <object>cur.address
                    proxy = self._proxy_for(address, cur)
                    item = (address, proxy)
                    # SET_ITEM steals a reference
                    Py_INCREF(<PyObject *>item)
                    PyList_SET_ITEM(values, out_idx, item)
                    out_idx += 1
        finally:
            if enabled:
                gc.enable()
        return values

    def itervalues(self):
        """Return an iterable of values stored in this map."""
        return _MOCValueIterator(self)

    def values(self):
        # This returns a list, but that is 'close enough' for what we need
        cdef long i
        cdef _MemObject *cur
        cdef _MemObjectProxy proxy

        values = []
        for i from 0 <= i < self._table_mask:
            cur = self._table[i]
            if cur == NULL or cur == _dummy:
                continue
            else:
                proxy = self._proxy_for(<object>cur.address, cur)
                values.append(proxy)
        return values


cdef class _MOCValueIterator:
    """A simple iterator over the values in a MOC."""

    cdef MemObjectCollection collection
    cdef int initial_active
    cdef int table_pos

    def __init__(self, collection):
        self.collection = collection
        self.initial_active = self.collection._active
        self.table_pos = 0

    def __iter__(self):
        return self

    def __next__(self):
        cdef _MemObject *cur

        if self.collection._active != self.initial_active:
            raise RuntimeError('MemObjectCollection changed size during'
                               ' iteration')
        while (self.table_pos <= self.collection._table_mask):
            cur = self.collection._table[self.table_pos]
            if cur != NULL and cur != _dummy:
                break
            self.table_pos += 1
        if self.table_pos > self.collection._table_mask:
            raise StopIteration()
        # This entry is 'consumed', go on to the next
        self.table_pos += 1
        if cur == NULL or cur == _dummy:
            raise RuntimeError('didn\'t run off the end, but got null/dummy'
                ' %d, %d %d' % (<int>cur, self.table_pos,
                                self.collection._table_mask))
        return self.collection._proxy_for(<object>cur.address, cur)


cdef class _MOPReferencedIterator:
    """Iterate over all the children referenced from this object."""

    cdef MemObjectCollection collection
    cdef object seen_addresses
    cdef list pending_addresses
    cdef int pending_offset

    def __init__(self, proxy, excluding=None):
        cdef _MemObjectProxy c_proxy

        from meliae import _intset
        c_proxy = proxy
        self.collection = c_proxy.collection
        if excluding is not None:
            self.seen_addresses = _intset.IDSet(excluding)
        else:
            self.seen_addresses = _intset.IDSet()
        self.pending_addresses = [c_proxy.address]
        self.pending_offset = 0

    def __iter__(self):
        return self

    def __next__(self):
        while self.pending_offset >= 0:
            next_address = self.pending_addresses[self.pending_offset]
            self.pending_offset -= 1
            # Avoid letting the pending addresses queue remain at its largest
            # size forever. If it has more that 50% waste, and it is 'big',
            # shrink it. Leave it a little room to grow, though.
            if (self.pending_offset > 50
                and len(self.pending_addresses) > 2*self.pending_offset):
                self.pending_addresses = self.pending_addresses[
                    :self.pending_offset+10]
            if next_address in self.seen_addresses:
                continue
            self.seen_addresses.add(next_address)
            next_proxy = self.collection.get(next_address)
            if next_proxy is None:
                continue
            # Queue up the children of this object
            for c in next_proxy.children:
                if c in self.seen_addresses:
                    continue
                self.pending_offset += 1
                if self.pending_offset >= len(self.pending_addresses):
                    self.pending_addresses.append(c)
                else:
                    self.pending_addresses[self.pending_offset] = c
            return next_proxy
        # if we got this far, then we don't have anything left:
        raise StopIteration()
