FROM nginx:alpine
MAINTAINER drmonkeysee <brandonrstansbury@gmail.com>

ENV APP_DIR=/opt/ecs-scheduler
WORKDIR $APP_DIR

RUN apk update \
	&& apk add python3 \
	&& apk add uwsgi \
	&& rm -rf /var/cache/apk/*

COPY requirements.txt $APP_DIR

RUN pip3 install -U pip setuptools
RUN pip3 install -r requirements.txt

COPY config/nginx.conf /etc/nginx/conf.d/ecs-scheduler.conf

COPY . $APP_DIR
RUN chmod u+x docker-run.sh

# TODO: use uwsgi and nginx
CMD ["./docker-run.sh"]
