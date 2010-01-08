# Copyright (C) 2010 Canonical Ltd
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

"""Routines for giving warnings."""

import warnings

_warn_func = warnings.warn


def deprecated(msg):
    """Issue a warning about something that is deprecated."""
    warn(msg, DeprecationWarning, stacklevel=3)


def warn(msg, klass=None, stacklevel=1):
    """Emit a warning about something."""
    _warn_func(msg, klass, stacklevel=stacklevel)


def trap_warnings(new_warning_func):
    """Redirect warnings to a different function.
    
    :param new_warning_func: A function with the same signature as warning.warn
    :return: The old warning function
    """
    global _warn_func
    old = _warn_func
    _warn_func = new_warning_func
    return old
