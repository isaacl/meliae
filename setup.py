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
        "description": "Dump Memory Content to disk for Python Programs",
        "author": "John Arbash Meinel",
        "author_email": "john.meinel@canonical.com",
        "url": "https://launchpad.net/meliae",
        "packages": ["meliae"],
        "scripts": ["strip_duplicates.py"],
        "ext_modules": ext
    }

    from distutils.core import setup, Extension

    try:
        from Pyrex.Distutils import build_ext
    except ImportError:
        print "We depend on having Pyrex installed."
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
