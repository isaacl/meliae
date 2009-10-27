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

"""A program to spawn a subprocess and track how memory is consumed."""

import subprocess
import time

def spawn_and_track(opts, args):
    from meliae import perf_counter
    timer = perf_counter.perf_counter.get_timer()
    start = timer()
    print 'spawning: %s' % (args,)
    # We have to use shell=False, otherwise we end up tracking the 'cmd.exe' or
    # 'sh' process, rather than the actual process we care about.
    p = subprocess.Popen(args, shell=False)
    mb = 1.0/(1024.0*1024)
    last = start
    last_print = 0
    mem_secs = 0
    while p.poll() is None:
        now = timer()
        cur_mem, peak_mem = perf_counter.perf_counter.get_memory(p)
        mem_secs += cur_mem * (now - last)
        last = now
        time.sleep(opts.sleep_time)
        if now - last_print > 3:
            print '%8.3fs %6.1fMB %6.1fMB %8.1fMB*s         \r' % (
                now - start, cur_mem*mb, peak_mem*mb, mem_secs*mb),
            last_print = now
    print '%8.3fs %6.1fMB %6.1fMB %8.1fMB*s          ' % (now - start,
        cur_mem*mb, peak_mem*mb, mem_secs*mb)


def main(args):
    import optparse
    p = optparse.OptionParser('%prog [local opts] command [opts]')
    p.add_option('--trace-file', type=str, default=None,
                 help='Save the memory usage information to this file')
    p.add_option('--sleep-time', type=float, default=0.1,
                 help='Check the status after this many seconds.')
    # All options after the first 'command' are passed to the command, so don't
    # try to process them ourselves.
    p.disable_interspersed_args()
    opts, args = p.parse_args(args)
    spawn_and_track(opts, args)


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
