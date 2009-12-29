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
    PyObject *Py_None
    void *PyMem_Malloc(size_t)
    void PyMem_Free(void *)

    long PyObject_Hash(PyObject *) except -1

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


ctypedef struct RefList:
    long size
    PyObject *refs[0]


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


cdef struct _MemObject:
    # """The raw C structure, used to minimize memory allocation size."""
    PyObject *address
    PyObject *type_str
    # Consider making this unsigned long
    long size
    RefList *ref_list
    # Removed for now, since it hasn't proven useful
    # int length
    PyObject *value
    # TODO: I don't think I've found an object that has both a value and a
    #       name. As such, I should probably remove the redundancy, as it saves
    #       a pointer
    # PyObject *name
    RefList *referrer_list
    unsigned long total_size
    # This is an uncounted ref to a _MemObjectProxy. _MemObjectProxy also has a
    # refreence to this object, so when it disappears it can set the reference
    # to NULL.
    PyObject *proxy


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
    _free_ref_list(cur.ref_list)
    cur.ref_list = NULL
    Py_XDECREF(cur.value)
    cur.value = NULL
    # Py_XDECREF(cur.name)
    # cur.name = NULL
    _free_ref_list(cur.referrer_list)
    cur.referrer_list = NULL
    cur.proxy = NULL
    PyMem_Free(cur)
    return 1


cdef _MemObject *_dummy
_dummy = <_MemObject*>(-1)


cdef class MemObjectCollection


cdef class _MemObjectProxy:
    """This class proxies between a real Python object and MOC's data.

    MOC stores the data as a fairly efficient table, without the overhead of
    having a regular python object for every data point. However, the rest of
    python code needs to interact with a real python object, so we generate
    these on-the-fly.
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
            else:
                fprintf(stderr, "obj at address %x referenced"
                    " a proxy that was not self\n",
                    <int><object>self._obj.address)
        if self._managed_obj != NULL:
            _free_mem_object(self._managed_obj)
            self._managed_obj = NULL

    property address:
        def __get__(self):
            return <object>(self._obj.address)

    property type_str:
        """The type of this object."""
        def __get__(self):
            return <object>(self._obj.type_str)

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
        if self._obj.ref_list == NULL:
            return 0
        return self._obj.ref_list.size

    property num_refs:
        def __get__(self):
            return self.__len__()

    def _intern_from_cache(self, cache):
        cdef long i
        _set_default_ptr(cache, &self._obj.address)
        _set_default_ptr(cache, &self._obj.type_str)
        if self._obj.ref_list != NULL:
            for i from 0 <= i < self._obj.ref_list.size:
                _set_default_ptr(cache, &self._obj.ref_list.refs[i])
        if self._obj.referrer_list != NULL:
            for i from 0 <= i < self._obj.referrer_list.size:
                _set_default_ptr(cache, &self._obj.referrer_list.refs[i])


    property ref_list:
        """The list of objects referenced by this object."""
        def __get__(self):
            return _ref_list_to_list(self._obj.ref_list)

        def __set__(self, value):
            _free_ref_list(self._obj.ref_list)
            self._obj.ref_list = _list_to_ref_list(value)

    property referrers:
        """The list of objects that reference this object.

        Original set to None, can be computed on demand.
        """
        def __get__(self):
            return _ref_list_to_list(self._obj.referrer_list)

        def __set__(self, value):
            _free_ref_list(self._obj.referrer_list)
            self._obj.referrer_list = _list_to_ref_list(value)

    property num_referrers:
        """The length of the referrers list."""
        def __get__(self):
            if self._obj.referrer_list == NULL:
                return 0
            return self._obj.referrer_list.size

    def __getitem__(self, offset):
        cdef long off

        if self._obj.ref_list == NULL:
            raise IndexError('%s has no references' % (self,))
        off = offset
        if off >= self._obj.ref_list.size:
            raise IndexError('%s has only %d (not %d) references'
                             % (self, self._obj.ref_list.size, offset))
        address = <object>self._obj.ref_list.refs[off]
        try:
            return self.collection[address]
        except KeyError:
            # TODO: What to do if the object isn't present? I think returning a
            #       'no-such-object' proxy would be nicer than returning nothing
            raise

    def __repr__(self):
        if self._obj.ref_list == NULL:
            refs = ''
        else:
            refs = ' %drefs' % (self._obj.ref_list.size,)
        if self._obj.referrer_list == NULL:
            referrers = ''
        else:
            referrers = ' %dpar' % (self._obj.referrer_list.size,)
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
            refs, referrers, val, total_size_str)


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


    def add(self, address, type_str, size, ref_list=(), length=0,
            value=None, name=None, referrer_list=(), total_size=0):
        """Add a new MemObject to this collection."""
        cdef _MemObject **slot, *new_entry
        cdef _MemObjectProxy proxy
        cdef PyObject *addr

        slot = self._lookup(address)
        if slot[0] != NULL and slot[0] != _dummy:
            # We are overwriting an existing entry, for now, fail
            # Probably all we have to do is clear the slot first, then continue
            assert False, "We don't support overwrite yet."
        # TODO: These are fairy small and more subject to churn, maybe we
        #       should be using PyObj_Malloc instead...
        new_entry = <_MemObject *>PyMem_Malloc(sizeof(_MemObject))
        if new_entry == NULL:
            # TODO: as we are running out of memory here, we might want to
            #       pre-allocate this object. Since it is likely to take as
            #       much mem to create this object as _MemObject
            raise MemoryError('Failed to allocate %d bytes'
                              % (sizeof(_MemObject),))
        memset(new_entry, 0, sizeof(_MemObject))
        addr = <PyObject *>address
        if slot[0] == NULL:
            self._filled += 1
        self._active += 1
        slot[0] = new_entry
        Py_INCREF(addr)
        new_entry.address = addr
        new_entry.type_str = <PyObject *>type_str
        Py_INCREF(new_entry.type_str)
        new_entry.size = size
        new_entry.ref_list = _list_to_ref_list(ref_list)
        # TODO: Scheduled for removal
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
        new_entry.referrer_list = _list_to_ref_list(referrer_list)
        new_entry.total_size = total_size

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
        cdef long i
        cdef _MemObject *cur
        cdef _MemObjectProxy proxy

        values = []
        for i from 0 <= i < self._table_mask:
            cur = self._table[i]
            if cur == NULL or cur == _dummy:
                continue
            else:
                address = <object>cur.address
                proxy = self._proxy_for(address, cur)
                values.append((address, proxy))
        return values

    def itervalues(self):
        """Return an iterable of values stored in this map."""
        return self.values()

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
    # TODO: Scheduled for removal
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

    def __len__(self):
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

