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

"""Work with files on disk."""

import errno
import gzip
try:
    import multiprocessing
except ImportError:
    multiprocessing = None
import subprocess
import sys


def open_file(filename):
    """Open a file which might be a regular file or a gzip.
    
    :return: An iterator of lines, and a cleanup function.
    """
    source = open(filename, 'r')
    gzip_source = gzip.GzipFile(mode='rb', fileobj=source)
    try:
        line = gzip_source.readline()
    except KeyboardInterrupt:
        raise
    except:
        # probably not a gzip file
        source.seek(0)
        return source, None
    else:
        gzip_source.close()
        source.close()
        # a gzip file
        # preference - a gzip subprocess
        if sys.platform == 'win32':
            close_fds = False # not supported
        else:
            close_fds = True
        try:
            process = subprocess.Popen(['gunzip', '-c', filename],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, close_fds=close_fds)
        except OSError, e:
            if e.errno == errno.ENOENT:
                # failing that, use another python process
                return _open_mprocess(filename)
        # make reading from stdin, or writting errors cause immediate aborts
        process.stdin.close()
        process.stderr.close()
        return process.stdout, process.terminate


def _stream_file(filename, child):
    gzip_source = gzip.GzipFile(filename, 'rb')
    for line in gzip_source:
        child.send(line)
    child.send(None)


def _open_mprocess(filename):
    if multiprocessing is None:
        # can't multiprocess, use inprocess gzip.
        return gzip.GzipFile(filename, mode='rb'), None
    parent, child = multiprocessing.Pipe(False)
    process = multiprocessing.Process(target=_stream_file, args=(filename, child))
    process.start()
    def iter_pipe():
        while True:
            line = parent.recv()
            if line is None:
                break
            yield line
    return iter_pipe(), process.join
