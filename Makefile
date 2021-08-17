PY := python3
VENV := venv
ACTIVATE := source $(VENV)/bin/activate
CONTAINER_NAME := ecs-scheduler

.PHONY: check clean docker docker-clean debug purge

ifndef LOG_LEVEL
LOG_LEVEL := INFO
endif
ifndef ECS_CLUSTER
ECS_CLUSTER := dev-cluster
endif
debug: $(VENV)
	$(ACTIVATE) && FLASK_DEBUG=1 FLASK_APP=ecsscheduler.py \
	ECSS_LOG_LEVEL=$(LOG_LEVEL) ECSS_ECS_CLUSTER=$(ECS_CLUSTER) flask run

check: $(VENV)
	$(ACTIVATE) && $(PY) -m unittest

$(VENV):
	$(PY) -m venv $@
	$(ACTIVATE) && pip install -U pip setuptools wheel
	$(ACTIVATE) && pip install -r requirements.txt

docker: check
	docker build -t $(CONTAINER_NAME) .

docker-clean:
	docker ps -a | awk '/$(CONTAINER_NAME)/ { print $$1 }' | xargs docker rm
	docker rmi $(CONTAINER_NAME)

clean:
	rm -rf .eggs build dist ecs_scheduler.egg-info
	find . -type d -path ./venv -prune -o -name __pycache__ -exec rm -rf {} \+

purge: clean
	rm -rf $(VENV)
