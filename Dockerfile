FROM nginx:alpine
MAINTAINER drmonkeysee <brandonrstansbury@gmail.com>

ENV APP_DIR=/opt/ecs-scheduler
WORKDIR $APP_DIR

RUN apk update \
	&& apk add python3
	&& apk add uwsgi

COPY requirements.txt $APP_DIR

RUN pip3 install -U pip setuptools
RUN pip3 install -r requirements.txt

COPY . $APP_DIR

EXPOSE 5000

# TODO: use uwsgi and nginx
CMD ["python3", "ecsscheduler.py"]
