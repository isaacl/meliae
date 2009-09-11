# Copyright (C) 2009 Canonical Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU General Public License and
# the GNU Lesser General Public License along with this program.  If
# not, see <http://www.gnu.org/licenses/>.

"""Take a given dump file, and bring the data back.

Currently requires simplejson to parse.
"""

import gzip
import math
try:
    import multiprocessing
except ImportError:
    nultiprocessing = None
import os
import re
import sys
import time

try:
    import simplejson
except ImportError:
    simplejson = None

from meliae import (
    files,
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
    refs = [int(val) for val in _refs_re.findall(refs)]
    obj = cls(address=int(address),
              type_str=type_str,
              size=int(size),
              ref_list=refs,
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

    def __init__(self, objs, show_progress=True):
        self.objs = objs
        self.show_progress = show_progress

    def compute_referrers(self):
        """For each object, figure out who is referencing it."""
        referrers = {} # From address => [referred from]
        id_cache = {}
        total = len(self.objs)
        for idx, obj in enumerate(self.objs.itervalues()):
            if self.show_progress and idx & 0x1ff == 0:
                sys.stderr.write('compute referrers %8d / %8d        \r'
                                 % (idx, total))
            address = obj.address
            address = id_cache.setdefault(address, address)
            for ref in obj.ref_list:
                ref = id_cache.setdefault(ref, ref)
                referrers.setdefault(ref, []).append(address)
        for obj in self.objs.itervalues():
            obj.referrers = referrers.get(obj.address, ())

    def remove_expensive_references(self):
        """Filter out references that are mere houskeeping links.

        module.__dict__ tends to reference lots of other modules, which in turn
        brings in the global reference cycle. Going further
        function.__globals__ references module.__dict__, so it *too* ends up in
        the global cycle. Generally these references aren't interesting, simply
        because they end up referring to *everything*.

        We filter out any reference to modules, frames, types, function globals
        pointers & LRU sideways references.
        """
        source = lambda:self.objs.itervalues()
        total_objs = len(self.objs)
        for changed, obj in remove_expensive_references(source, total_objs,
            self.show_progress):
            if changed:
                self.objs[obj.address] = obj

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
        total = len(self.objs)
        break_on = total / 10
        for idx, obj in enumerate(self.objs.itervalues()):
            if self.show_progress and idx & 0x1ff == 0:
                sys.stderr.write('compute size %8d / %8d        \r'
                                 % (idx, total))
            pending_descendents = list(obj.ref_list)
            seen = _intset.IDSet()
            seen.add(obj.address)
            total_size = obj.size
            while pending_descendents:
                next_ref = pending_descendents.pop()
                if next_ref in seen:
                    continue
                seen.add(next_ref)
                next_obj = self.objs.get(next_ref, None)
                if next_obj is None:
                    continue
                # type and frame types tend to cause us to recurse into
                # everything. So for now, when we encounter them, don't add
                # their references
                total_size += next_obj.size
                pending_descendents.extend([ref for ref in next_obj.ref_list
                                                 if ref not in seen])
            ## count = len(seen)
            ## # This single object references more than 10% of all objects, and
            ## # expands to more that 10x its direct references
            ## if count > obj.num_refs * 10 and count > break_on:
            ##     import pdb; pdb.set_trace()
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
    :param using_json: Use simplejson rather than the regex. This allows
        arbitrary ordered json dicts to be parsed but still requires per-line
        layout.
    """
    cleanup = None
    if isinstance(source, str):
        source, cleanup = files.open_file(source)
        if isinstance(source, file):
            input_size = os.fstat(source.fileno()).st_size
        else:
            input_size = 0
    elif isinstance(source, (list, tuple)):
        input_size = sum(map(len, source))
    else:
        input_size = 0
    try:
        return _load(source, using_json, show_prog, input_size)
    finally:
        if cleanup is not None:
            cleanup()


def iter_objs(source, using_json=False, show_prog=False, input_size=0, objs=None):
    """Iterate MemObjects from json.

    :param source: A line iterator.
    :param using_json: Use simplejson. See load().
    :param show_prog: Show progress.
    :param input_size: The size of the input if known (in bytes) or 0.
    :param objs: Either None or a dict containing objects by address. If not
        None, then duplicate objects will not be parsed or output.
    :return: A generator of MemObjects.
    """
    # TODO: cStringIO?
    tstart = time.time()
    input_mb = input_size / 1024. / 1024.
    temp_cache = {}
    address_re = re.compile(
        r'{"address": (?P<address>\d+)'
        )
    bytes_read = count = 0
    last = 0
    mb_read = 0
    if using_json:
        decoder = _from_json
    else:
        decoder = _from_line
    for line_num, line in enumerate(source):
        bytes_read += len(line)
        if line in ("[\n", "]\n"):
            continue
        if line.endswith(',\n'):
            line = line[:-2]
        if objs:
            # Skip duplicate objects
            m = address_re.match(line)
            if not m:
                continue
            address = int(m.group('address'))
            if address in objs:
                continue
        yield decoder(_loader.MemObject, line, temp_cache=temp_cache)
        if show_prog and (line_num - last > 5000):
            last = line_num
            mb_read = bytes_read / 1024. / 1024
            tdelta = time.time() - tstart
            sys.stderr.write(
                'loading... line %d, %d objs, %5.1f / %5.1f MiB read in %.1fs\r'
                % (line_num, len(objs), mb_read, input_mb, tdelta))
    if show_prog:
        mb_read = bytes_read / 1024. / 1024
        tdelta = time.time() - tstart
        sys.stderr.write(
            'loaded line %d, %d objs, %5.1f / %5.1f MiB read in %.1fs        \n'
            % (line_num, len(objs), mb_read, input_mb, tdelta))


def _load(source, using_json, show_prog, input_size):
    objs = {}
    for memobj in iter_objs(source, using_json, show_prog, input_size, objs):
        objs[memobj.address] = memobj
    # _fill_total_size(objs)
    return ObjManager(objs, show_progress=show_prog)


def remove_expensive_references(source, total_objs=0, show_progress=False):
    """Filter out references that are mere houskeeping links.

    module.__dict__ tends to reference lots of other modules, which in turn
    brings in the global reference cycle. Going further
    function.__globals__ references module.__dict__, so it *too* ends up in
    the global cycle. Generally these references aren't interesting, simply
    because they end up referring to *everything*.

    We filter out any reference to modules, frames, types, function globals
    pointers & LRU sideways references.

    :param source: A callable that returns an iterator of MemObjects. This
        will be called twice.
    :param total_objs: The total objects to be filtered, if known. If
        show_progress is False or the count of objects is unknown, 0.
    :return: An iterator of (changed, MemObject) objects with expensive
        references removed.
    """
    # First pass, find objects we don't want to reference any more
    noref_objs = _intset.IDSet()
    lru_objs = _intset.IDSet()
    total_steps = total_objs * 2
    seen_zero = False
    for idx, obj in enumerate(source()):
        # 'module's have a single __dict__, which tends to refer to other
        # modules. As you start tracking into that, you end up getting into
        # reference cycles, etc, which generally ends up referencing every
        # object in memory.
        # 'frame' also tends to be self referential, and a single frame
        # ends up referencing the entire current state
        # 'type' generally is self referential through several attributes.
        # __bases__ means we recurse all the way up to object, and object
        # has __subclasses__, which means we recurse down into all types.
        # In general, not helpful for debugging memory consumption
        if show_progress and idx & 0x1ff == 0:
            sys.stderr.write('finding expensive refs... %8d / %8d    \r'
                             % (idx, total_steps))
        if obj.type_str in ('module', 'frame', 'type'):
            noref_objs.add(obj.address)
        if obj.type_str == '_LRUNode':
            lru_objs.add(obj.address)
        if obj.address == 0:
            seen_zero = True
    # Second pass, any object which refers to something in noref_objs will
    # have that reference removed, and replaced with the null_memobj
    num_expensive = len(noref_objs)
    null_memobj = _loader.MemObject(0, '<ex-reference>', 0, [])
    if not seen_zero:
        yield (True, null_memobj)
    for idx, obj in enumerate(source()):
        if show_progress and idx & 0x1ff == 0:
            sys.stderr.write('removing %d expensive refs... %8d / %8d   \r'
                             % (num_expensive, idx + total_objs,
                                total_steps))
        if obj.type_str == 'function':
            # Functions have a reference to 'globals' which is not very
            # helpful for having a clear understanding of what is going on
            # especially since the function itself is in its own globals
            # XXX: This is probably not a guaranteed order, but currently
            #       func_traverse returns:
            #   func_code, func_globals, func_module, func_defaults,
            #   func_doc, func_name, func_dict, func_closure
            # We want to remove the reference to globals and module
            refs = list(obj.ref_list)
            obj.ref_list = refs[:1] + refs[3:] + [0]
            yield (True, obj)
            continue
        elif obj.type_str == '_LRUNode':
            # We remove the 'sideways' references
            obj.ref_list = [ref for ref in obj.ref_list
                                 if ref not in lru_objs]
            yield (True, obj)
            continue
        for ref in obj.ref_list:
            if ref in noref_objs:
                break
        else:
            # No bad references, keep going
            yield (False, obj)
            continue
        new_ref_list = [ref for ref in obj.ref_list
                             if ref not in noref_objs]
        new_ref_list.append(0)
        obj.ref_list = new_ref_list
        yield (True, obj)
    if show_progress:
        sys.stderr.write('removed %d expensive refs from %d objs%s\n'
                         % (num_expensive, total_objs, ' '*20))
