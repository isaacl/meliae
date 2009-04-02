def config():
    ext = []
    kwargs = {
        "name": "memory_dump",
        "version": "0.1.1",
        "description": "Dump Memory Content to disk for Python Programs",
        "author": "John Arbash Meinel",
        "author_email": "john.meinel@canonical.com",
        "url": "https://launchpad.net/pymemorydump",
        "packages": ["memory_dump"],
        "ext_modules": ext
    }

    from distutils.core import setup, Extension

    try:
        from Pyrex.Distutils import build_ext
    except ImportError:
        print "We depend on having Pyrex installed."
        return

    kwargs["cmdclass"] = {"build_ext": build_ext}
    ext.append(Extension("memory_dump._scanner",
                         ["memory_dump/_scanner.pyx",
                          "memory_dump/_scanner_core.c"]))

    setup(**kwargs)

if __name__ == "__main__":
    config()
