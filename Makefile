CURRENT_PY := $(shell which python3)
VENV_PY := $(PWD)/venv/bin/python3
PY := python3

define VENV_ERROR
Must activate virtual environment:
	python3 -m venv venv
	source venv/bin/activate
	pip install -U pip setuptools
	pip install -r requirements.txt
Execute the above if virtual env is not set up
endef

.PHONY: venv build check test clean

build:
	$(PY) setup.py bdist_wheel

check: build
	$(PY) setup.py test

clean:
	rm -rf .eggs build dist ecs_scheduler.egg-info

docker: build
	echo 'Build docker container'

docker-clean:
	echo 'Remove docker artifacts'

test: venv
	$(PY) -m unittest

venv:
ifneq ($(CURRENT_PY), $(VENV_PY))
	$(error $(VENV_ERROR))
endif
