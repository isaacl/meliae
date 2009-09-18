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

"""Remove expensive references.

This script takes 1 or two filenames and filters the first into either std out,
or the second filename.
"""

import os
import re
import sys
import time

from meliae import files, loader


def main(args):
    import optparse
    p = optparse.OptionParser(
        '%prog INFILE [OUTFILE]')

    opts, args = p.parse_args(args)
    if len(args) > 2:
        sys.stderr.write('We only support 2 filenames, not %d\n' % (len(args),))
        return -1
    if len(args) < 1:
        sys.stderr.write("Must supply INFILE\n")
        return -1

    def source():
        infile, cleanup = files.open_file(args[0])
        for obj in loader.iter_objs(infile):
            yield obj
        cleanup()
    if len(args) == 1:
        outfile = sys.stdout
    else:
        outfile = open(args[1], 'wb')
    for _, obj in loader.remove_expensive_references(source, show_progress=True):
        outfile.write(obj.to_json() + '\n')   
    outfile.flush()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

