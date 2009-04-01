# Copyright (C) 2009 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Helpers for loading and running the test suite."""

import unittest

TestCase = unittest.TestCase


def run_suite():
    runner = unittest.TextTestRunner()
    suite = test_suite()
    return runner.run(suite)


def test_suite():
    module_names = [
        ]
    full_names = [__name__ + '.' + n for n in module_names]

    loader = unittest.TestLoader()
    suite = loader.suiteClass()
    for full_name in full_names:
        module = __import__(full_name, {}, {}, [None])
        suite.addTests(loader.loadTestsFromModule(module))
    return suite
