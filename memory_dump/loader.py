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

"""Take a given dump file, and bring the data back.

Currently requires simplejson to parse.
"""

try:
    import simplejson
except ImportError:
    simplejson = None


class MemObject(object):
    """This maintains the state of a given memory object."""

    __slots__ = ('address', 'type_str', 'size', 'ref_list', 'length',
                 'value', 'name', 'total_size')

    def __init__(self, address, type_str, size, ref_list, length=None,
                 value=None, name=None):
        self.address = address
        self.type_str = type_str
        self.size = size
        self.ref_list = ref_list
        self.length = length
        self.value = value
        self.name = name
        self.total_size = None

    def __repr__(self):
        if self.name is not None:
            name_str = ', %s' % (self.name,)
        else:
            name_str = ''
        if self.total_size is None:
            total_bytes = -1
        else:
            total_bytes = self.total_size
        return ('%s(%08x, %s%s, %d bytes, %d refs, %s total)'
                % (self.__class__.__name__, self.address, self.type_str,
                   name_str, self.size, len(self.ref_list), total_bytes))

    @classmethod
    def from_json_dict(cls, val):
        # simplejson likes to turn everything into unicode strings, but we know
        # everything is just a plain 'str', and we can save some bytes if we
        # cast it back
        obj = cls(address=val['address'],
                  type_str=str(val['type']),
                  size=val['size'],
                  ref_list=val['refs'],
                  length=val.get('len', None),
                  value=val.get('value', None),
                  name=val.get('name', None))
        if (obj.type_str == 'str'):
            obj.value = str(obj.value)
        return obj


def _fill_total_size(objs):
    """Fill out the total_size record for objs."""
    for obj in objs.itervalues():
        if obj.total_size is not None:
            continue
        stack_set = set([obj])
        stack = [obj]
        while stack:
            next = stack[-1]
            if next.total_size is not None:
                stack.pop()
                continue
            total_size = next.size
            all_refs_satisfied = True
            for ref in next.ref_list:
                ref_obj = objs[ref]
                if ref_obj.total_size is None:
                    if ref_obj not in stack_set:
                        all_refs_satisfied = False
                        stack.append(ref_obj)
                        stack_set.add(ref_obj)
                    else:
                        # refs that are already in the queue, are considered
                        # 'satisfied', because we will come back and fill them
                        # out later
                        pass
                else:
                    total_size += ref_obj.total_size
            if all_refs_satisfied:
                # We have handled all refs, this item is done
                next.total_size = total_size
                stack.pop()


def load(fname):
    obj_list = simplejson.load(open(fname))
    objs = {}
    for obj in obj_list:
        if not obj: # Skip the one empty object
            continue
        address = obj['address']
        if address in objs: # Skip duplicate objects
            continue
        objs[address] = MemObject.from_json_dict(obj)
