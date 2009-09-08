#!/usr/bin/env python
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

"""Run the pysizer test suite."""

import sys


def main(args):
    import optparse
    p = optparse.OptionParser()
    p.add_option('--verbose', '-v', action='store_true',
                 help='run verbose tests')

    (opts, args) = p.parse_args(args)
    import meliae.tests
    return not meliae.tests.run_suite(verbose=opts.verbose)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
