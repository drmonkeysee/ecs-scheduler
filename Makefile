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

.PHONY: check clean docker docker-clean venv debug

ifndef LOG_LEVEL
LOG_LEVEL := INFO
endif
ifndef ECS_CLUSTER
ECS_CLUSTER := dev-cluster
endif
debug: venv
	FLASK_DEBUG=1 FLASK_APP=ecsscheduler.py ECSS_LOG_LEVEL=$(LOG_LEVEL) ECSS_ECS_CLUSTER=$(ECS_CLUSTER) flask run

check: venv
	$(PY) -m unittest

venv:
ifneq ($(CURRENT_PY), $(VENV_PY))
	$(error $(VENV_ERROR))
endif

docker: check
	docker build -t $(CONTAINER_NAME) .

docker-clean:
	docker ps -a | awk '/$(CONTAINER_NAME)/ { print $$1 }' | xargs docker rm
	docker rmi $(CONTAINER_NAME)

clean:
	rm -rf .eggs build dist ecs_scheduler.egg-info
	find . -type d -path ./venv -prune -o -name __pycache__ -exec rm -rf {} \+
