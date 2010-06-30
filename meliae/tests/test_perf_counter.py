# Copyright (C) 2009, 2010 Canonical Ltd
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

import subprocess
import sys

from meliae import (
    perf_counter,
    tests,
    )


class _FakeTimer(object):

    def __init__(self):
        self._current = 0.0

    def __call__(self):
        self._current += 0.5
        return self._current


class Test_Counter(tests.TestCase):

    def test_tick_tock(self):
        counter = perf_counter._Counter('test', _FakeTimer())
        counter.tick()
        counter.tock()
        self.assertEqual(1, counter.count)
        self.assertEqual(0.5, counter.time_spent)
        self.assertEqual(0.0, counter.time_stddev())
        counter.tock()
        self.assertEqual(2, counter.count)
        self.assertEqual(0.5, counter.time_spent)



class TestPerformanceCounter(tests.TestCase):

    def setUp(self):
        super(TestPerformanceCounter, self).setUp()
        perf_counter.perf_counter.reset()

    def tearDown(self):
        perf_counter.perf_counter.reset()
        super(TestPerformanceCounter, self).tearDown()

    def test_perf_counter_is_not_none(self):
        self.assertNotEqual(None, perf_counter.perf_counter)

    def test_create_counter(self):
        counter = perf_counter.perf_counter.get_counter('test-counter')
        self.assertEqual('test-counter', counter.name)
        self.assertEqual(counter._timer, perf_counter.perf_counter.get_timer())
        self.assertTrue('test-counter' in perf_counter.perf_counter._counters)

    def test_get_counter(self):
        counter = perf_counter.perf_counter.get_counter('test-counter')
        counter2 = perf_counter.perf_counter.get_counter('test-counter')
        self.assertTrue(counter is counter2)

    def test_get_memory(self):
        # we don't have a great way to actually measure that the peak-memory
        # value is accurate, but we can at least try
        # Create a very large string, and then delete it.
        p = subprocess.Popen([sys.executable, '-c',
            'x = "abcd"*(10*1000*1000); del x;'
            'import sys;'
            'sys.stdout.write(sys.stdin.read(3));'
            'sys.stdout.flush();'
            'sys.stdout.write(sys.stdin.read(4));'
            'sys.stdout.flush(); sys.stdout.close()'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p.stdin.write('pre')
        p.stdin.flush()
        p.stdout.read(3)
        cur_mem, peak_mem = perf_counter.perf_counter.get_memory(p)
	if cur_mem is None or peak_mem is None:
	    # fail gracefully, though we may want a stronger assertion here
	    return
        self.assertTrue(isinstance(cur_mem, (int, long)))
        self.assertTrue(isinstance(peak_mem, (int, long)))
        p.stdin.write('post')
        p.stdin.flush()
        p.stdout.read()
        self.assertEqual(0, p.wait())
        # We allocated a 40MB string, we should have peaked at at least 20MB more
        # than we are using now.
        self.assertTrue(peak_mem > cur_mem + 2*1000*1000)
