/* Copyright (C) 2009 Canonical Ltd
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License and
 * the GNU Lesser General Public License along with this program.  If
 * not, see <http://www.gnu.org/licenses/>.
 */

/* The core of parsing is split into a pure C module, so that we can guarantee
 * that we won't be creating objects in the internal loops.
 */

#include "_scanner_core.h"


struct ref_info {
    FILE *out;
    int first;
    PyObject *nodump;
};

Py_ssize_t
_basic_object_size(PyObject *c_obj)
{
    Py_ssize_t size;
    size = c_obj->ob_type->tp_basicsize;
    if (PyType_HasFeature(c_obj->ob_type, Py_TPFLAGS_HAVE_GC)) {
        size += sizeof(PyGC_Head);
    }
    return size;
}


Py_ssize_t
_var_object_size(PyVarObject *c_obj)
{
    Py_ssize_t num_entries;
    num_entries = PyObject_Size((PyObject *)c_obj);
    if (num_entries < 0) {
        /* This object doesn't support len() */
        num_entries = 0;
        PyErr_Clear();
    }
    return _basic_object_size((PyObject *)c_obj)
            + num_entries * c_obj->ob_type->tp_itemsize;
}


Py_ssize_t
_size_of_list(PyListObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    size += sizeof(PyObject*) * c_obj->allocated;
    return size;
}


Py_ssize_t
_size_of_set(PySetObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    if (c_obj->table != c_obj->smalltable) {
        size += sizeof(setentry) * (c_obj->mask + 1);
    }
    return size;
}


Py_ssize_t
_size_of_dict(PyDictObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    if (c_obj->ma_table != c_obj->ma_smalltable) {
        size += sizeof(PyDictEntry) * (c_obj->ma_mask + 1);
    }
    return size;
}


Py_ssize_t
_size_of_unicode(PyUnicodeObject *c_obj)
{
    Py_ssize_t size;
    size = _basic_object_size((PyObject *)c_obj);
    size += Py_UNICODE_SIZE * c_obj->length;
    return size;
}


Py_ssize_t
_size_of(PyObject *c_obj)
{
    if PyList_Check(c_obj) {
        return _size_of_list((PyListObject *)c_obj);
    } else if PyAnySet_Check(c_obj) {
        return _size_of_set((PySetObject *)c_obj);
    } else if PyDict_Check(c_obj) {
        return _size_of_dict((PyDictObject *)c_obj);
    } else if PyUnicode_Check(c_obj) {
        return _size_of_unicode((PyUnicodeObject *)c_obj);
    }

    if (c_obj->ob_type->tp_itemsize != 0) {
        // Variable length object with inline storage
        // total size is tp_itemsize * ob_size
        return _var_object_size((PyVarObject *)c_obj);
    }
    return _basic_object_size(c_obj);
}


int
_dump_reference(PyObject *c_obj, void* val)
{
    struct ref_info *out;
    out = (struct ref_info*)val;
    if (out->first) {
        out->first = 0;
        fprintf(out->out, "%lu", (unsigned long)c_obj);
    } else {
        fprintf(out->out, ", %lu", (unsigned long)c_obj);
    }
    return 0;
}


int
_dump_child(PyObject *c_obj, void *val)
{
    struct ref_info *info;
    info = (struct ref_info *)val;
    // The caller has asked us to dump self, but no recursive children
    _dump_object_info(info->out, c_obj, info->nodump, 0);
    return 0;
}


int
_dump_if_no_traverse(PyObject *c_obj, void *val)
{
    struct ref_info *info;
    info = (struct ref_info *)val;
    /* Objects without traverse are simple things without refs, and built-in
     * types have a traverse, but they won't be part of gc.get_objects().
     */
    if (Py_TYPE(c_obj)->tp_traverse == NULL
        || (PyType_Check(c_obj)
            && !PyType_HasFeature((PyTypeObject*)c_obj, Py_TPFLAGS_HEAPTYPE)))
    {
        _dump_object_info(info->out, c_obj, info->nodump, 0);
    }
    // We know that it is safe to recurse here, because tp_traverse is NULL
    return 0;
}


void
_dump_json_c_string(FILE *out, const char *buf, Py_ssize_t len)
{
    Py_ssize_t i;
    char c;

    // Never try to dump more than this many chars
    if (len == -1) {
        len = strlen(buf);
    }
    if (len > 100) {
        len = 100;
    }
    fprintf(out, "\"");
    for (i = 0; i < len; ++i) {
        c = buf[i];
        if (c <= 0x1f || c > 0x7e) { // use the unicode escape sequence
            fprintf(out, "\\u00%02x", ((unsigned short)c & 0xFF));
        } else if (c == '\\' || c == '/' || c == '"') {
            fprintf(out, "\\%c", c);
        } else {
            fprintf(out, "%c", c);
        }
    }
    fprintf(out, "\"");
}

void
_dump_string(FILE *out, PyObject *c_obj)
{
    // TODO: consider writing to a small memory buffer, before writing to disk
    Py_ssize_t str_size;
    char *str_buf;

    str_buf = PyString_AS_STRING(c_obj);
    str_size = PyString_GET_SIZE(c_obj);

    _dump_json_c_string(out, str_buf, str_size);
}


void
_dump_unicode(FILE *out, PyObject *c_obj)
{
    // TODO: consider writing to a small memory buffer, before writing to disk
    Py_ssize_t uni_size;
    Py_UNICODE *uni_buf, c;
    Py_ssize_t i;

    uni_buf = PyUnicode_AS_UNICODE(c_obj);
    uni_size = PyUnicode_GET_SIZE(c_obj);

    // Never try to dump more than this many chars
    if (uni_size > 100) {
        uni_size = 100;
    }
    fprintf(out, "\"");
    for (i = 0; i < uni_size; ++i) {
        c = uni_buf[i];
        if (c <= 0x1f || c > 0x7e) {
            fprintf(out, "\\u%04x", ((unsigned short)c & 0xFFFF));
        } else if (c == '\\' || c == '/' || c == '"') {
            fprintf(out, "\\%c", (unsigned char)c);
        } else {
            fprintf(out, "%c", (unsigned char)c);
        }
    }
    fprintf(out, "\"");
}


void
_dump_object_info(FILE *out, PyObject *c_obj, PyObject *nodump, int recurse)
{
    Py_ssize_t size;
    struct ref_info info;
    int retval;

    info.out = out;
    info.nodump = nodump; /* Stealing the reference, but not permanently */

    if (nodump != Py_None && PyAnySet_Check(nodump)) {
        if (c_obj == nodump) {
            /* Don't dump the 'nodump' set. */
            return;
        }
        retval = PySet_Contains(nodump, c_obj);
        if (retval == 1) {
            /* This object is part of the no-dump set, don't dump the object */
            return;
        } else if (retval == -1) {
            /* An error was raised, but we don't care, ignore it */
            PyErr_Clear();
        }
    }

    size = _size_of(c_obj);
    fprintf(out, "{\"address\": %lu, \"type\": ", (unsigned long)c_obj);
    _dump_json_c_string(out, c_obj->ob_type->tp_name, -1);
    fprintf(out, ", \"size\": %d", _size_of(c_obj));
    //  HANDLE __name__
    if (PyModule_Check(c_obj)) {
        fprintf(out, ", \"name\": ");
        _dump_json_c_string(out, PyModule_GetName(c_obj), -1);
    } else if (PyFunction_Check(c_obj)) {
        fprintf(out, ", \"name\": ");
        _dump_string(out, ((PyFunctionObject *)c_obj)->func_name);
    } else if (PyType_Check(c_obj)) {
        fprintf(out, ", \"name\": ");
        _dump_json_c_string(out, ((PyTypeObject *)c_obj)->tp_name, -1);
    } else if (PyClass_Check(c_obj)) {
        /* Old style class */
        fprintf(out, ", \"name\": ");
        _dump_string(out, ((PyClassObject *)c_obj)->cl_name);
    }
    if (PyString_Check(c_obj)) {
        fprintf(out, ", \"len\": %d", PyString_GET_SIZE(c_obj));
        fprintf(out, ", \"value\": ");
        _dump_string(out, c_obj);
    } else if (PyUnicode_Check(c_obj)) {
        fprintf(out, ", \"len\": %d", PyUnicode_GET_SIZE(c_obj));
        fprintf(out, ", \"value\": ");
        _dump_unicode(out, c_obj);
    } else if (PyInt_CheckExact(c_obj)) {
        fprintf(out, ", \"value\": %ld", PyInt_AS_LONG(c_obj));
    } else if (PyTuple_Check(c_obj)) {
        fprintf(out, ", \"len\": %d", PyTuple_GET_SIZE(c_obj));
    } else if (PyList_Check(c_obj)) {
        fprintf(out, ", \"len\": %d", PyList_GET_SIZE(c_obj));
    } else if (PyAnySet_Check(c_obj)) {
        fprintf(out, ", \"len\": %d", PySet_GET_SIZE(c_obj));
    } else if (PyDict_Check(c_obj)) {
        fprintf(out, ", \"len\": %d", PyDict_Size(c_obj));
    }
    fprintf(out, ", \"refs\": [");
    if (Py_TYPE(c_obj)->tp_traverse != NULL) {
        info.first = 1;
        Py_TYPE(c_obj)->tp_traverse(c_obj, _dump_reference, &info);
    }
    fprintf(out, "]}\n");
    if (Py_TYPE(c_obj)->tp_traverse != NULL && recurse != 0) {
        if (recurse == 2) { /* Always dump one layer deeper */
            Py_TYPE(c_obj)->tp_traverse(c_obj, _dump_child, &info);
        } else if (recurse == 1) {
            /* strings and such aren't in gc.get_objects, so we need to dump
             * them when they are referenced.
             */
            Py_TYPE(c_obj)->tp_traverse(c_obj, _dump_if_no_traverse, &info);
        }
    }
}

static int
_append_object(PyObject *visiting, void* data)
{
    PyObject *lst;
    lst = (PyObject *)data;
    if (lst == NULL) {
        return -1;
    }
    if (PyList_Append(data, visiting) == -1) {
        return -1;
    }
    return 0;
}
/**
 * Return a PyList of all objects referenced via tp_traverse.
 */
PyObject *_get_referents(PyObject *c_obj)
{
    PyObject *lst;

    lst = PyList_New(0);
    if (lst == NULL) {
        return NULL;
    }
    if (Py_TYPE(c_obj)->tp_traverse != NULL) {
        Py_TYPE(c_obj)->tp_traverse(c_obj, _append_object, lst);
    }
    return lst;
}
