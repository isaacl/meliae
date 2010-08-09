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


def config():
    import meliae
    ext = []
    kwargs = {
        "name": "meliae",
        "version": meliae.__version__,
        "description": "Python Memory Usage Analyzer",
        "author": "John Arbash Meinel",
        "author_email": "john.meinel@canonical.com",
        "url": "https://launchpad.net/meliae",
        "license": "GNU GPL v3",
        "download_url": "https://launchpad.net/meliae/+download",
        "packages": ["meliae"],
        "scripts": ["strip_duplicates.py"],
        "ext_modules": ext,
        "classifiers": [
            'Development Status :: 4 - Beta',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Operating System :: OS Independent',
            'Operating System :: Microsoft :: Windows',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Programming Language :: Cython',
            'Topic :: Software Development :: Debuggers',
        ],
        "long_description": """\
This project is similar to heapy (in the 'guppy' project), in its attempt to
understand how memory has been allocated.

Currently, its main difference is that it splits the task of computing summary
statistics, etc of memory consumption from the actual scanning of memory
consumption. It does this, because I often want to figure out what is going on
in my process, while my process is consuming huge amounts of memory (1GB, etc).
It also allows dramatically simplifying the scanner, as I don't allocate python
objects while trying to analyze python object memory consumption.

It will likely grow to include a GUI for browsing the reference graph. For now
it is mostly used in the python interpreter.

The name is simply a fun word (means Ash-wood Nymph). 
"""
    }

    from distutils.core import setup, Extension

    try:
        from Cython.Distutils import build_ext
    except ImportError:
        print "We require Cython to be installed."
        return

    kwargs["cmdclass"] = {"build_ext": build_ext}
    ext.append(Extension("meliae._scanner",
                         ["meliae/_scanner.pyx",
                          "meliae/_scanner_core.c"]))
    ext.append(Extension("meliae._loader",
                         ["meliae/_loader.pyx"]))
    ext.append(Extension("meliae._intset",
                         ["meliae/_intset.pyx"]))

    setup(**kwargs)

if __name__ == "__main__":
    config()
