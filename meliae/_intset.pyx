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

"""A structure for handling a set of pure integers.

(Such as a set of python object ids.)
"""

cdef extern from *:
    ctypedef unsigned long size_t
    void *malloc(size_t)
    void *realloc(void *, size_t)
    void free(void *)
    void memset(void *, int, size_t)


ctypedef size_t int_type
cdef int_type _singleton1, _singleton2
# _singleton1 is the 'no value present' value
# _singleton2 is the 'value deleted' value, which has us keep searching
# collisions after the fact
_singleton1 = <int_type> 0;
_singleton2 = <int_type> -1;


cdef class IntSet:
    """Keep a set of integer objects.

    This is slightly more efficient than a PySet because we don't allow
    arbitrary types.
    """

    cdef Py_ssize_t _count
    cdef Py_ssize_t _mask
    cdef int_type *_array
    cdef readonly int _has_singleton

    def __init__(self, values=None):
        self._count = 0
        self._mask = 0
        self._array = NULL
        # This is a separate bit mask of singletons that we have seen
        # There are 2, the one which indicates no value, and the one that
        # indicates 'dummy', aka removed value
        self._has_singleton = 0
        if values:
            for value in values:
                self._add(value)

    def __dealloc__(self):
        if self._array != NULL:
            free(self._array)

    def __len__(self):
        return self._count

    def _peek_array(self):
        cdef Py_ssize_t i, size
        if self._array == NULL:
            return None
        result = []
        size = self._mask + 1
        for i from 0 <= i < size:
            result.append(self._array[i])
        return result

    cdef int_type *_lookup(self, int_type c_val) except NULL:
        """Taken from the set() algorithm."""
        cdef size_t offset, perturb
        cdef int_type *entry, *freeslot

        if self._array == NULL:
            raise RuntimeError('cannot _lookup without _array allocated.')
        offset = c_val & self._mask
        entry = self._array + offset
        if entry[0] == c_val or entry[0] == _singleton1:
            return entry
        if entry[0] == _singleton2:
            freeslot = entry
        else:
            freeslot = NULL

        perturb = c_val
        while True:
            offset = (offset << 2) + offset + perturb + 1
            entry = self._array + (offset & self._mask)
            if (entry[0] == _singleton1):
                # We converged on an empty slot, without finding entry == c_val
                # If we previously found a freeslot, return it, else return
                # this entry
                if freeslot == NULL:
                    return entry
                else:
                    return freeslot
            elif (entry[0] == c_val):
                # Exact match
                return entry
            elif (entry[0] == _singleton2 and freeslot == NULL):
                # We found the first match that was a 'dummy' entry
                freeslot = entry
            perturb = perturb >> 5 # PERTURB_SHIFT

    def __contains__(self, val):
        cdef int_type c_val, *entry
        c_val = val
        if c_val == _singleton1:
            if self._has_singleton & 0x01:
                return True
            else:
                return False
        elif c_val == _singleton2:
            if self._has_singleton & 0x02:
                return True
            else:
                return False
        if self._array == NULL:
            return False
        entry = self._lookup(c_val)
        if entry[0] == c_val:
            return True
        return False

    cdef int _grow(self) except -1:
        cdef int i
        cdef Py_ssize_t old_mask, old_size, new_size, old_count
        cdef int_type *old_array, val

        old_mask = self._mask
        old_size = old_mask + 1
        old_array = self._array
        old_count = self._count
        # Current size * 2
        if old_array == NULL: # Nothing currently allocated
            self._mask = 255
            self._array = <int_type*>malloc(sizeof(int_type) * 256)
            memset(self._array, _singleton1, sizeof(int_type) * 256)
            return 0
        new_size = old_size * 2
        # Replace 'in place', grow to a new array, and add items back in
        # Note that if it weren't for collisions, we could actually 'realloc()'
        # and insert backwards. Since expanding mask means something will only
        # fit in its old place, or the 2<<1 greater.
        self._array = <int_type*>malloc(sizeof(int_type) * new_size)
        memset(self._array, _singleton1, sizeof(int_type) * new_size)
        self._mask = new_size - 1
        self._count = 0
        if self._has_singleton & 0x01:
            self._count = self._count + 1
        if self._has_singleton & 0x02:
            self._count = self._count + 1
        for i from 0 <= i < old_size:
            val = old_array[i]
            if val != _singleton1 and val != _singleton2:
                self._add(val)
        if self._count != old_count:
            raise RuntimeError('After resizing array from %d => %d'
                ' the count of items changed %d => %d'
                % (old_size, new_size, old_count, self._count))
        free(old_array)

    cdef int _add(self, int_type c_val) except -1:
        cdef int_type *entry
        if c_val == _singleton1:
            if self._has_singleton & 0x01:
                return 0
            self._has_singleton = self._has_singleton | 0x01
            self._count = self._count + 1
            return 1
        elif c_val == _singleton2:
            if self._has_singleton & 0x02:
                # Already had it, no-op
                return 0
            self._has_singleton = self._has_singleton | 0x02
            self._count = self._count + 1
            return 1
        if self._array == NULL or self._count * 4 > self._mask:
            self._grow()
        entry = self._lookup(c_val)
        if entry[0] == c_val:
            # We already had it, no-op
            return 0
        if entry[0] == _singleton1 or entry[0] == _singleton2:
            # No value stored at this location
            entry[0] = c_val
            self._count = self._count + 1
            return 1
        raise RuntimeError("Calling self._lookup(%x) returned %x. However"
            " that is not the value or one of the singletons."
            % (c_val, entry[0]))

    def add(self, val):
        self._add(val)


cdef class IDSet(IntSet):
    """Track a set of object ids (addresses).

    This only differs from IntSet in how the integers are hashed. Object
    addresses tend to be aligned on 16-byte boundaries (occasionally 8-byte,
    and even more rarely on 4-byte), as such the standard hash lookup has more
    collisions than desired.
    """

    cdef int_type *_lookup(self, int_type c_val) except NULL:
        """Taken from the set() algorithm."""
        cdef size_t offset, perturb
        cdef int_type *entry, *freeslot
        cdef int_type internal_val

        if self._array == NULL:
            raise RuntimeError('cannot _lookup without _array allocated.')
        # For addresses, we shift the last 4 bits into the beginning of the
        # value
        internal_val = ((c_val & 0xf) << (sizeof(int_type)*8 - 4))
        internal_val = internal_val | (c_val >> 4)
        offset = internal_val & self._mask
        entry = self._array + offset
        if entry[0] == c_val or entry[0] == _singleton1:
            return entry
        if entry[0] == _singleton2:
            freeslot = entry
        else:
            freeslot = NULL

        perturb = c_val
        while True:
            offset = (offset << 2) + offset + perturb + 1
            entry = self._array + (offset & self._mask)
            if (entry[0] == _singleton1):
                # We converged on an empty slot, without finding entry == c_val
                # If we previously found a freeslot, return it, else return
                # this entry
                if freeslot == NULL:
                    return entry
                else:
                    return freeslot
            elif (entry[0] == c_val):
                # Exact match
                return entry
            elif (entry[0] == _singleton2 and freeslot == NULL):
                # We found the first match that was a 'dummy' entry
                freeslot = entry
            perturb = perturb >> 5 # PERTURB_SHIFT

