/* Copyright (C) 2009, 2010 Canonical Ltd
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
 */

/* The core of parsing is split into a pure C module, so that we can guarantee
 * that we won't be creating objects in the internal loops.
 */

#ifndef _SCANNER_CORE_H_
#define _SCANNER_CORE_H_

#include <Python.h>
#include <code.h>
#include <frameobject.h>
#include <stdio.h>

/**
 * Compute the size of the data directly addressed by this object.
 *
 * For example, for a list, this is the number of bytes allocated plus the
 * number of bytes for the basic list object. Note that lists over-allocate, so
 * this is not strictly sizeof(pointer) * num_items.
 */
extern Py_ssize_t _size_of(PyObject *c_obj);

/**
 * This callback will be used to dump more info to the user.
 */
typedef void (*write_callback)(void *data, const char *bytes, size_t len);

/**
 * Write the information about this object to the file.
 */
extern void _dump_object_info(write_callback write, void *callee_data,
                              PyObject *c_obj, PyObject *nodump, int recurse);

/**
 * Clear out what the last object we dumped was.
 */
extern void _clear_last_dumped();

/**
 * Return a PyList of all objects referenced via tp_traverse.
 */
extern PyObject *_get_referents(PyObject *c_obj);


#endif // _SCANNER_CORE_H_

