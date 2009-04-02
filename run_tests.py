#!/usr/bin/env python
"""Run the pysizer test suite."""

import sys


def main(args):
    import optparse
    p = optparse.OptionParser()
    p.add_option('--verbose', '-v', action='store_true',
                 help='run verbose tests')

    (opts, args) = p.parse_args(args)
    import memory_dump.tests
    return not memory_dump.tests.run_suite(verbose=opts.verbose)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
