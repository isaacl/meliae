#!/usr/bin/env python
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

"""Remove duplicated object information.

To be memory efficient, 'scanner.dump_gc_objects()' does not track what objects
have already been dumped. This means that it occasionally dumps the same object
multiple times.
This script just takes 2 files, and filters the incoming one into purely unique
lines in the outgoing one.
"""

import os
import re
import sys
import time

from meliae import files


def strip_duplicate(infile, outfile, insize=None):
    from meliae import _intset
    seen = _intset.IntSet()

    address_re = re.compile(
        r'{"address": (?P<address>\d+)'
        )
    if insize is not None:
        in_mb = ' / %5.1f MiB' % (insize / 1024. / 1024,)
    else:
        in_mb = ''
    bytes_read = 0
    last_bytes = 0
    lines_out = 0
    tstart = time.time()
    tlast = time.time()
    for line_num, line in enumerate(infile):
        bytes_read += len(line)
        m = address_re.match(line)
        if m:
            address = int(m.group('address'))
            if address not in seen:
                outfile.write(line)
                lines_out += 1
                seen.add(address)
        tnow = time.time()
        if tnow - tlast > 0.2:
            tlast = tnow
            mb_read = bytes_read / 1024. / 1024
            tdelta = tnow - tstart
            sys.stderr.write(
                'loading... line %d, %d out, %5.1f%s read in %.1fs\r'
                % (line_num, lines_out, mb_read, in_mb, tdelta))


def main(args):
    import optparse
    p = optparse.OptionParser(
        '%prog [INFILE [OUTFILE]]')

    opts, args = p.parse_args(args)
    if len(args) > 2:
        sys.stderr.write('We only support 2 filenames, not %d\n' % (len(args),))
        return -1

    cleanups = []
    try:
        if len(args) == 0:
            infile = sys.stdin
            insize = None
            outfile = sys.stdout
        else:
            infile, cleanup = files.open_file(args[0])
            if cleanup is not None:
                cleanups.append(cleanup)
            if isinstance(infile, file):
                # pipes are files, but 0 isn't useful.
                insize = os.fstat(infile.fileno()).st_size or None
            else:
                insize = None
            if len(args) == 1:
                outfile = sys.stdout
            else:
                outfile = open(args[1], 'wb')
        strip_duplicate(infile, outfile, insize)
    finally:
        for cleanup in cleanups:
            cleanup()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

