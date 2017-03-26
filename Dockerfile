FROM python:3-alpine
MAINTAINER drmonkeysee <brandonrstansbury@gmail.com>

ENV APP_DIR=/opt/ecs_scheduler
WORKDIR $APP_DIR

ENV LOG_LEVEL=WARNING
ENV RUN_ENV=local
ENV COMPONENT_NAME=webapi

COPY requirements.txt $APP_DIR

RUN pip install -r requirements.txt

COPY . $APP_DIR

EXPOSE 5000

CMD ["./ecsscheduler"]
