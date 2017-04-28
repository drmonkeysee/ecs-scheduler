FROM python:3-alpine
MAINTAINER drmonkeysee <brandonrstansbury@gmail.com>

ENV APP_DIR=/opt/ecs-scheduler
WORKDIR $APP_DIR

COPY requirements.txt $APP_DIR

RUN pip install -r requirements.txt

ENV LOG_LEVEL=WARNING
ENV RUN_ENV=localdocker
ENV COMPONENT=webapi

COPY . $APP_DIR

EXPOSE 5000

CMD ["python", "ecsscheduler.py"]
