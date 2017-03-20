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

.PHONY: venv check

check: venv
	$(PY) -m unittest

venv:
ifneq ($(CURRENT_PY), $(EXPECTED_BIN))
	$(error $(VENV_ERROR))
endif

