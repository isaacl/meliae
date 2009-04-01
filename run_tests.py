#!/usr/bin/env python
"""Run the pysizer test suite."""

import sys


def main(args):
    import optparse
    p = optparse.OptionParser()

    (opts, args) = p.parse_args(args)
    import memory_dump.tests
    return not memory_dump.tests.run_suite()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
