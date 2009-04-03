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

import os
import re
import sys

try:
    import simplejson
except ImportError:
    simplejson = None

from memory_dump import _loader

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


def _from_json(cls, line, temp_cache=None):
    val = simplejson.loads(line)
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


def _from_line(cls, line, temp_cache=None):
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


def load(source, using_json=False, show_prog=True):
    """Load objects from the given source.

    :param source: If this is a string, we will open it as a file and read all
        objects. For any other type, we will simply iterate and parse objects
        out, so the object should be an iterator of json lines.
    """
    if isinstance(source, str):
        source = open(source, 'r')
        input_size = os.fstat(source.fileno()).st_size
    elif isinstance(source, (list, tuple)):
        input_size = sum(map(len, source))
    # TODO: cStringIO?
    input_mb = input_size / 1024. / 1024.
    objs = {}
    temp_cache = {}
    address_re = re.compile(
        r'{"address": (?P<address>\d+)'
        )
    bytes_read = count = 0
    last = 0

    for line_num, line in enumerate(source):
        bytes_read += len(line)
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
            memobj = _from_json(_loader.MemObject, line, temp_cache=temp_cache)
        else:
            memobj = _from_line(_loader.MemObject, line, temp_cache=temp_cache)
        objs[memobj.address] = memobj
        if show_prog and (line_num - last > 5000):
            last = line_num
            mb_read = bytes_read / 1024. / 1024
            sys.stdout.write(
                'loading... line %d, %d objs, %5.1f / %5.1f MiB read\r'
                % (line_num, len(objs), mb_read, input_mb))
    if show_prog:
        sys.stdout.write(
            'loaded line %d, %d objs, %5.1f / %5.1f MiB read        \n'
            % (line_num, len(objs), mb_read, input_mb))
    # _fill_total_size(objs)
    return objs
