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

"""Some bits for helping to scan objects looking for referenced memory."""

import gc

from memory_dump import (
    _intset,
    _scanner,
    )


def dump_all_referenced(outf, obj):
    """Recursively dump everything that is referenced from obj."""
    # if isinstance(outf, str):
    #     outf = open(outf, 'wb')
    outf.write("[\n")
    pending = [obj]
    seen = _intset.IntSet()
    while pending:
        next = pending.pop()
        id_next = id(next)
        if id_next in seen:
            continue
        seen.add(id_next)
        _scanner.dump_object_info(outf, next)
        for ref in gc.get_referents(next):
            if id(ref) not in seen:
                pending.append(ref)
    # We close with an empty object so that we can write valid JSON with
    # everything having a trailing ','
    outf.write("{}\n]\n")


def dump_gc_objects(outf):
    """Dump everything that is available via gc.objects().

    This does *not* do a recursive search.
    """
    if isinstance(outf, basestring):
        outf = open(outf, 'wb')
    outf.write("[\n")
    # None isn't in gc.get_objects(), for some reason we've been having
    # problems not traversing to find it.
    _scanner.dump_object_info(outf, None)
    for obj in gc.get_objects():
        _scanner.dump_object_info(outf, obj)
    # We close with an empty object so that we can write valid JSON with
    # everything having a trailing ','
    outf.write("{}\n]\n")
