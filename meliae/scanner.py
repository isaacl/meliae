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

"""Some bits for helping to scan objects looking for referenced memory."""

import gc
import types

from meliae import (
    _intset,
    _scanner,
    )


size_of = _scanner.size_of
get_referents = _scanner.get_referents


def dump_all_referenced(outf, obj, is_pending=False):
    """Recursively dump everything that is referenced from obj."""
    if isinstance(outf, str):
        outf = open(outf, 'wb')
    if is_pending:
        pending = obj
    else:
        pending = [obj]
    last_offset = len(pending) - 1
    seen = _intset.IDSet()
    while last_offset >= 0:
        next = pending[last_offset]
        last_offset -= 1
        id_next = id(next)
        if id_next in seen:
            continue
        seen.add(id_next)
        # We will recurse here, so tell dump_object_info to not recurse
        _scanner.dump_object_info(outf, next, recurse_depth=0)
        for ref in get_referents(next):
            if id(ref) not in seen:
                last_offset += 1
                if len(pending) > last_offset:
                    pending[last_offset] = ref
                else:
                    pending.append(ref)


def dump_gc_objects(outf, recurse_depth=1):
    """Dump everything that is available via gc.get_objects().
    """
    if isinstance(outf, basestring):
        opened = True
        outf = open(outf, 'wb')
    else:
        opened = False
    # Get the list of everything before we start building new objects
    all_objs = gc.get_objects()
    # Dump out a few specific objects, so they don't get repeated forever
    nodump = [None, True, False]
    # In current versions of python, these are all pre-cached
    nodump.extend(xrange(-5, 256))
    nodump.extend([chr(c) for c in xrange(256)])
    nodump.extend([t for t in types.__dict__.itervalues()
                      if type(t) is types.TypeType])
    nodump.extend([set, dict])
    # Some very common interned strings
    nodump.extend(('__doc__', 'self', 'operator', '__init__', 'codecs',
                   '__new__', '__builtin__', '__builtins__', 'error', 'len',
                   'errors', 'keys', 'None', '__module__', 'file', 'name', '',
                   'sys', 'True', 'False'))
    nodump.extend((BaseException, Exception, StandardError, ValueError))
    for obj in nodump:
        _scanner.dump_object_info(outf, obj, nodump=None, recurse_depth=0)
    # Avoid dumping the all_objs list and this function as well. This helps
    # avoid getting a 'reference everything in existence' problem.
    nodump.append(dump_gc_objects)
    # This currently costs us ~16kB during dumping, but means we won't write
    # out those objects multiple times in the log file.
    # TODO: we might want to make nodump a variable-size dict, and add anything
    #       with ob_refcnt > 1000 or so.
    nodump = frozenset(nodump)
    for obj in all_objs:
        _scanner.dump_object_info(outf, obj, nodump=nodump,
                                  recurse_depth=recurse_depth)
    del all_objs[:]
    if opened:
        outf.close()
    else:
        outf.flush()


def dump_all_objects(outf):
    """Dump everything that is referenced from gc.get_objects()

    This recurses, and tracks dumped objects in an IDSet. Which means it costs
    memory, which is often about 10% of currently active memory. Otherwise,
    this usually results in smaller dump files than dump_gc_objects().

    This also can be faster, because it doesn't dump the same item multiple
    times.
    """
    if isinstance(outf, basestring):
        opened = True
        outf = open(outf, 'wb')
    else:
        opened = False
    all_objs = gc.get_objects()
    dump_all_referenced(outf, all_objs, is_pending=True)
    del all_objs[:]
    if opened:
        outf.close()
    else:
        outf.flush()



def get_recursive_size(obj):
    """Get the memory referenced from this object.

    This returns the memory of the direct object, and all of the memory
    referenced by child objects. It also returns the total number of objects.
    """
    total_size = 0
    pending = [obj]
    last_item = 0
    seen = _intset.IDSet()
    size_of = _scanner.size_of
    while last_item >= 0:
        item = pending[last_item]
        last_item -= 1
        id_item = id(item)
        if id_item in seen:
            continue
        seen.add(id_item)
        total_size += size_of(item)
        for child in get_referents(item):
            if id(child) not in seen:
                last_item += 1
                if len(pending) > last_item:
                    pending[last_item] = child
                else:
                    pending.append(child)
    return len(seen), total_size


def get_recursive_items(obj):
    """Walk all referred items and return the unique list of them."""
    all = []
    pending = [obj]
    last_item = 0
    seen = _intset.IDSet()
    while last_item >= 0:
        item = pending[last_item]
        last_item -= 1
        id_item = id(item)
        if id_item in seen:
            continue
        seen.add(id_item)
        all.append(item)
        for child in get_referents(item):
            if id(child) not in seen:
                last_item += 1
                if len(pending) > last_item:
                    pending[last_item] = child
                else:
                    pending.append(child)
    return all


def find_interned_dict():
    """Go through all gc objects and find the interned python dict."""
    for obj in gc.get_objects():
        if (type(obj) is not dict
            or 'find_interned_dict' not in obj
            or obj['find_interned_dict'] is not 'find_interned_dict'
            or 'get_recursive_items' not in obj
            or obj['get_recursive_items'] is not 'get_recursive_items'):
            # The above check assumes that local strings will be interned,
            # which is the standard cpython behavior, but perhaps not the best
            # to require? However, if we used something like a custom string
            # that we intern() we still could have problems with locals(), etc.
            continue
        return obj
