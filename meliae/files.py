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
    source = open(filename, 'rb')
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
        # We don't need these anymore, so close them out in case the rest of
        # the code raises an exception.
        gzip_source.close()
        source.close()
        # a gzip file
        # preference - a gzip subprocess
        if sys.platform == 'win32':
            close_fds = False # not supported
        else:
            close_fds = True
        try:
            process = subprocess.Popen(['gzip', '-d', '-c', filename],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, close_fds=close_fds)
        except OSError, e:
            if e.errno == errno.ENOENT:
                # failing that, use another python process
                return _open_mprocess(filename)
        # make reading from stdin, or writting errors cause immediate aborts
        process.stdin.close()
        process.stderr.close()
        terminate = getattr(process, 'terminate', None)
        # terminate is a py2.6 thing
        if terminate is not None:
            return process.stdout, terminate
        else:
            # We would like to use process.wait() but that can cause a deadlock
            # if the child is still writing.
            # The other alternative is process.communicate, but we closed
            # stderr, and communicate wants to read from it. (We get:
            #  ValueError: I/O operation on closed file
            # if we try it here. Also, for large files, this may be many GB
            # worth of data.
            # So for now, live with the deadlock...
            return process.stdout, process.wait


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
