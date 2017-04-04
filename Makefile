CURRENT_PY := $(shell which python3)
VENV_PY := $(PWD)/venv/bin/python3
PY := python3
CONTAINER_NAME := ecs-scheduler

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

docker: #build
	docker build -t $(CONTAINER_NAME) .

docker-clean:
	docker ps -a | awk '/$(CONTAINER_NAME)/ { print $$1 }' | xargs docker rm
	docker rmi $(CONTAINER_NAME)

test: venv
	$(PY) -m unittest

venv:
ifneq ($(CURRENT_PY), $(VENV_PY))
	$(error $(VENV_ERROR))
endif
