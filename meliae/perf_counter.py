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

"""Get information from the OS about current memory usage"""

import ctypes
import math
import sys
import time


class _Counter(object):
    """Track various aspects of performance for a given action."""

    def __init__(self, name, timer):
        self.name = name
        self.time_spent = 0.0
        self._time_spent_squared = 0.0
        self.count = 0
        self._time_start = None
        self._timer = timer

    def tick(self):
        """Indicate that we are starting a section related to this counter."""
        self._time_start = self._timer()

    def tock(self):
        """Indicate that we finished processing."""
        if self._time_start is not None:
            now = self._timer()
            delta = now - self._time_start
            self.time_spent += delta
            self._time_spent_squared += (delta * delta)
            self._time_start = None
        self.count += 1

    def time_stddev(self):
        # This uses a simple transformation on stddev to allow us to store 2
        # numbers and compute the standard deviation, rather than needing a
        # list of times.
        # stddev = sqrt(mean(x^2) - mean(x)^2)
        if self.count == 0:
            return 0
        diff = (self._time_spent_squared - (self.time_spent*self.time_spent))
        if self.count == 1:
            return math.sqrt(diff)
        return math.sqrt(diff / (self.count-1))



class PerformanceCounter(object):
    """Abstract some system information about performance counters.

    This includes both memory and timing.
    """

    def __init__(self):
        self._counters = {}

    def reset(self):
        self._counters.clear()

    def get_counter(self, name):
        """Create a Counter object that will track some aspect of processing.
        
        :param name: An identifier associated with this action.
        :return: A Counter instance.
        """
        try:
            c = self._counters[name]
        except KeyError:
            c = _Counter(name, self.get_timer())
            self._counters[name] = c
        return c

    def get_memory(self, process):
        """Ask the OS for the peak memory consumption at this point in time.

        :param process: is a subprocess.Popen object.
        :return: (current, peak) the memory used in bytes.
        """
        raise NotImplementedError(self.get_memory)


class _LinuxPerformanceCounter(PerformanceCounter):

    def get_timer(self):
        # This returns wall-clock time
        return time.time


class _Win32PerformanceCounter(PerformanceCounter):

    def get_timer(self):
        # This returns wall-clock time, but using a much higher precision than
        # time.time() [which has a resolution of only 15ms]
        return time.clock

    def _get_memory_win32(self, process_handle):
        """Get the current memory consumption using win32 apis."""
        mem_struct = PROCESS_MEMORY_COUNTERS_EX()
        ret = ctypes.windll.psapi.GetProcessMemoryInfo(process_handle,
            ctypes.byref(mem_struct),
            ctypes.sizeof(mem_struct))
        if not ret:
            raise RuntimeError('Failed to call GetProcessMemoryInfo: %s'
                               % ctypes.FormatError())
        return {
            'PageFaultCount': mem_struct.PageFaultCount,
            'PeakWorkingSetSize': mem_struct.PeakWorkingSetSize,
            'WorkingSetSize': mem_struct.WorkingSetSize,
            'QuotaPeakPagedPoolUsage': mem_struct.QuotaPeakPagedPoolUsage,
            'QuotaPagedPoolUsage': mem_struct.QuotaPagedPoolUsage,
            'QuotaPeakNonPagedPoolUsage': mem_struct.QuotaPeakNonPagedPoolUsage,
            'QuotaNonPagedPoolUsage': mem_struct.QuotaNonPagedPoolUsage,
            'PagefileUsage': mem_struct.PagefileUsage,
            'PeakPagefileUsage': mem_struct.PeakPagefileUsage,
            'PrivateUsage': mem_struct.PrivateUsage,
        }

    def get_memory(self, process):
        """See PerformanceCounter.get_memory()"""
        process_handle = int(process._handle)
        mem = self._get_memory_win32(process_handle)
        return mem['WorkingSetSize'], mem['PeakWorkingSetSize']


# what to do about darwin, freebsd, etc?
if sys.platform == 'win32':
    perf_counter = _Win32PerformanceCounter()
    # Define this here so we don't have to re-define it on every function call
    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        """Used by GetProcessMemoryInfo"""
        _fields_ = [('cb', ctypes.c_ulong),
                    ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                    ('PrivateUsage', ctypes.c_size_t),
                   ]
else:
    perf_counter = _LinuxPerformanceCounter()


def _get_process_win32():
    """Similar to getpid() but returns an OS handle."""
    return ctypes.windll.kernel32.GetCurrentProcess()
