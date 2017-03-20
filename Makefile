VENV := venv
CURRENT_PY := $(shell which python3)
EXPECTED_BIN := $(PWD)/$(VENV)/bin/python3
PY := python3

define VENV_ERROR
Must activate virtual environment:
	python3 -m venv venv
	source venv/bin/activate
	pip install -U pip setuptools
	pip install -r requirements.txt
Execute the above if virtual env is not set up
endef

.PHONY: venv build check test

# build wheel package
build:
	$(PY) setup.py bdist_wheel

# execute tests via setup
check: build
	$(PY) setup.py test

# execute tests in development environment
test: venv
	$(PY) -m unittest

# verify virtual env is set
venv:
ifneq ($(CURRENT_PY), $(EXPECTED_BIN))
	$(error $(VENV_ERROR))
endif
