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

"""Some bits for helping to scan objects looking for referenced memory."""

import gc
import types

from meliae import (
    _intset,
    _scanner,
    )


def dump_all_referenced(outf, obj):
    """Recursively dump everything that is referenced from obj."""
    # if isinstance(outf, str):
    #     outf = open(outf, 'wb')
    pending = [obj]
    seen = _intset.IDSet()
    while pending:
        next = pending.pop()
        id_next = id(next)
        if id_next in seen:
            continue
        seen.add(id_next)
        # We will recurse here, so tell dump_object_info to not recurse
        _scanner.dump_object_info(outf, next, recurse_depth=0)
        for ref in gc.get_referents(next):
            if id(ref) not in seen:
                pending.append(ref)


def dump_gc_objects(outf, recurse_depth=1):
    """Dump everything that is available via gc.objects().

    This does *not* do a recursive search.
    """
    if isinstance(outf, basestring):
        outf = open(outf, 'wb')
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
