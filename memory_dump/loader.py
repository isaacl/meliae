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

import math
import os
import re
import sys
import time

try:
    import simplejson
except ImportError:
    simplejson = None

from memory_dump import (
    _intset,
    _loader,
    )

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


class _TypeSummary(object):
    """Information about a given type."""

    def __init__(self, type_str):
        self.type_str = type_str
        self.count = 0
        self.total_size = 0
        self.sq_sum = 0 # used for stddev computation
        self.max_size = 0
        self.max_address = None

    def __repr__(self):
        if self.count == 0:
            avg = 0
            stddev = 0
        else:
            avg = self.total_size / float(self.count)
            exp_x2 = self.sq_sum / float(self.count)
            stddev = math.sqrt(exp_x2 - avg*avg)
        return '%s: %d, %d bytes, %.3f avg bytes, %.3f std dev, %d max @ %d' % (
            self.type_str, self.count, self.total_size, avg, stddev,
            self.max_size, self.max_address)

    def _add(self, memobj):
        self.count += 1
        self.total_size += memobj.size
        self.sq_sum += (memobj.size * memobj.size)
        if memobj.size > self.max_size:
            self.max_size = memobj.size
            self.max_address = memobj.address


class _ObjSummary(object):
    """Tracks the summary stats about objects listed."""

    def __init__(self):
        self.type_summaries = {}
        self.total_count = 0
        self.total_size = 0
        self.summaries = None

    def _add(self, memobj):
        try:
            type_summary = self.type_summaries[memobj.type_str]
        except KeyError:
            type_summary = _TypeSummary(memobj.type_str)
            self.type_summaries[memobj.type_str] = type_summary
        type_summary._add(memobj)
        self.total_count += 1
        self.total_size += memobj.size

    def __repr__(self):
        if self.summaries is None:
            self.by_size()
        out = [
            'Total %d objects, %d types, Total size = %.1fMiB (%d bytes)'
            % (self.total_count, len(self.summaries), self.total_size / 1024. / 1024,
               self.total_size),
            ' Index   Count   %      Size   % Cum     Max Kind'
            ]
        cumulative = 0
        for i in xrange(20):
            summary = self.summaries[i]
            cumulative += summary.total_size
            out.append(
                '%6d%8d%4d%10d%4d%4d%8d %s'
                % (i, summary.count, summary.count * 100.0 / self.total_count,
                   summary.total_size,
                   summary.total_size * 100.0 / self.total_size,
                   cumulative * 100.0 / self.total_size, summary.max_size,
                   summary.type_str))
        return '\n'.join(out)

    def by_size(self):
        summaries = sorted(self.type_summaries.itervalues(),
                           key=lambda x: (x.total_size, x.count),
                           reverse=True)
        self.summaries = summaries


class ObjManager(object):
    """Manage the collection of MemObjects.

    This is the interface for doing queries, etc.
    """

    def __init__(self, objs):
        self.objs = objs

    def compute_referrers(self):
        """For each object, figure out who is referencing it."""
        referrers = {} # From address => [referred from]
        id_cache = {}
        for obj in self.objs.itervalues():
            address = obj.address
            address = id_cache.setdefault(address, address)
            for ref in obj.ref_list:
                ref = id_cache.setdefault(ref, ref)
                referrers.setdefault(ref, []).append(address)
        for obj in self.objs.itervalues():
            obj.referrers = referrers.get(obj.address, ())

    def compute_total_size(self):
        """This computes the total bytes referenced from this object."""
        # Unfortunately, this is an N^2 operation :(. The problem is that
        # a.total_size + b.total_size != c.total_size (if c references a & b).
        # This is because a & b may refer to common objects. Consider something
        # like:
        #   A   _
        #  / \ / \
        # B   C  |
        #  \ /  /
        #   D--'
        # D & C participate in a refcycle, and B has an alternative path to D.
        # You certainly don't want to count D 2 times when computing the total
        # size of A. Also, how do you give the relative contribution of B vs C
        # in this graph?
        for obj in self.objs.itervalues():
            pending_descendents = list(obj.ref_list)
            seen = _intset.IntSet()
            seen.add(obj.address)
            total_size = obj.size
            while pending_descendents:
                next = pending_descendents.pop()
                if next in seen:
                    continue
                seen.add(next)
                next_obj = self.objs[next]
                total_size += next_obj.size
                pending_descendents.extend(next_obj.ref_list)
            obj.total_size = total_size

    def summarize(self):
        summary = _ObjSummary()
        for obj in self.objs.itervalues():
            summary._add(obj)
        return summary


def load(source, using_json=False, show_prog=True):
    """Load objects from the given source.

    :param source: If this is a string, we will open it as a file and read all
        objects. For any other type, we will simply iterate and parse objects
        out, so the object should be an iterator of json lines.
    """
    tstart = time.time()
    if isinstance(source, str):
        source = open(source, 'r')
        input_size = os.fstat(source.fileno()).st_size
    elif isinstance(source, (list, tuple)):
        input_size = sum(map(len, source))
    else:
        input_size = 0
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
            tdelta = time.time() - tstart
            sys.stdout.write(
                'loading... line %d, %d objs, %5.1f / %5.1f MiB read in %.1fs\r'
                % (line_num, len(objs), mb_read, input_mb, tdelta))
    if show_prog:
        tdelta = time.time() - tstart
        sys.stdout.write(
            'loaded line %d, %d objs, %5.1f / %5.1f MiB read in %.1fs        \n'
            % (line_num, len(objs), mb_read, input_mb, tdelta))
    # _fill_total_size(objs)
    return ObjManager(objs)
