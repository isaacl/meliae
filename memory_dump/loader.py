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

import re

try:
    import simplejson
except ImportError:
    simplejson = None

# This is the minimal regex that is guaranteed to match. In testing, it is
# about 3x faster than using simplejson, it is just less generic.
_object_re = re.compile(
    r'\{"address": (?P<address>\d+)'
    r', "type": "(?P<type>.*)"'
    r', "size": (?P<size>\d+)'
    r'(, "name": "(?P<name>.*)")?'
    r'(, "len": (?P<len>\d+))?'
    r'(, "value": (?P<value>.*))?'
    r', "refs": \[(?P<refs>[^]]*)\]'
    r'\}')

_refs_re = re.compile(
    r'(?P<ref>\d+)'
    )


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

    def _intern_from_cache(self, cache):
        """Intern values that we know are likely to not be unique."""
        self.address = cache.setdefault(self.address, self.address)
        self.type_str = cache.setdefault(self.type_str, self.type_str)
        self.size = cache.setdefault(self.size, self.size)
        self.ref_list = tuple([cache.setdefault(ref, ref)
                                 for ref in self.ref_list])

    @classmethod
    def from_json_dict(cls, val, temp_cache=None):
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
            if type(obj.value) is unicode:
                obj.value = obj.value.encode('latin-1')
        if temp_cache is not None:
            obj._intern_from_cache(temp_cache)
        return obj

    @classmethod
    def from_line(cls, line, temp_cache=None):
        m = _object_re.match(line)
        if not m:
            raise RuntimeError('Failed to parse line: %r' % (line,))
        (address, type_str, size, name, length, value,
         refs) = m.group('address', 'type', 'size', 'name', 'len',
                         'value', 'refs')
        assert '\\' not in type_str
        if name is not None:
            assert '\\' not in name
        if length is not None:
            length = int(length)
        obj = cls(address=int(address),
                  type_str=type_str,
                  size=int(size),
                  ref_list=[int(val) for val in _refs_re.findall(refs)],
                  length=length,
                  value=value,
                  name=name)
        if (obj.type_str == 'str'):
            if type(obj.value) is unicode:
                obj.value = obj.value.encode('latin-1')
        if temp_cache is not None:
            obj._intern_from_cache(temp_cache)
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


def load(fname, using_json=False):
    f = open(fname, 'r')
    objs = {}
    temp_cache = {}
    address_re = re.compile(
        r'{"address": (?P<address>\d+)'
        )
    address = 1
    for line in open(fname):
        if line in ("[\n", "]\n"):
            continue
        if line.endswith(',\n'):
            line = line[:-2]
        m = address_re.match(line)
        if not m:
            continue
        address = int(m.group('address'))
        if address in objs: # Skip duplicate objects
            continue
        if using_json:
            obj = simplejson.loads(line)
            if not obj: # Skip an one empty object
                continue
            memobj = MemObject.from_json_dict(obj, temp_cache=temp_cache)
        else:
            memobj = MemObject.from_line(line, temp_cache=temp_cache)
        objs[memobj.address] = memobj
    del temp_cache
    # _fill_total_size(objs)
    return objs
