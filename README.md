Meliae
======

A simple program for dumping python memory usage information to a disk format, which can then be parsed into useful things like graph representations.

It will likely grow to include a GUI for browsing the reference graph. For now it is mostly used in the python interpreter.

The name is simply a fun word (means Ash-wood Nymph).

## vs. heapy

This project is similar to heapy (in the 'guppy' project), in its attempt to understand how memory has been allocated.

Currently, its main difference is that it splits the task of computing summary statistics, etc of memory consumption from the actual scanning of memory consumption. It does this, because I often want to figure out what is going on in my process, while my process is consuming huge amounts of memory (1GB, etc). It also allows dramatically simplifying the scanner, as I don't allocate python objects while trying to analyze python object memory consumption.

## Code history

This repository was created from the [Meliae launchpad project](https://launchpad.net/meliae) with:

    bzr fast-export --git-branch=launchpad-trunk lp:meliae | git fast-import

The [launchpad-trunk branch](https://github.com/isaacl/meliae/tree/launchpad-dev) contains the state of code from the import.