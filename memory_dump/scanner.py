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
import types

from memory_dump import (
    _intset,
    _scanner,
    )


def dump_all_referenced(outf, obj):
    """Recursively dump everything that is referenced from obj."""
    # if isinstance(outf, str):
    #     outf = open(outf, 'wb')
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


def dump_gc_objects(outf, recurse_depth=1):
    """Dump everything that is available via gc.objects().

    This does *not* do a recursive search.
    """
    if isinstance(outf, basestring):
        outf = open(outf, 'wb')
    for obj in gc.get_objects():
        _scanner.dump_object_info(outf, obj, recurse_depth=recurse_depth)
