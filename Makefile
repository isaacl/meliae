all: build_inplace

check:
	python run_tests.py

build_inplace:
	python setup.py build_ext -i

.PHONY: all build_inplace
