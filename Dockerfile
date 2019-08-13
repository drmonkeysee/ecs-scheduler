FROM nginx:alpine
MAINTAINER drmonkeysee <brandonrstansbury@gmail.com>

ENV TZ=Etc/UTC
ENV APP_DIR=/opt/ecs-scheduler
WORKDIR $APP_DIR

RUN apk update \
	&& apk add python3 uwsgi uwsgi-python3 \
	&& rm -rf /var/cache/apk/*

RUN pip3 install -U pip setuptools
COPY requirements.txt $APP_DIR
RUN pip3 install -r requirements.txt

COPY config/nginx.conf /etc/nginx/conf.d/ecss.conf
COPY config/cors.conf /etc/nginx/cors.conf
COPY config/uwsgi.ini /etc/uwsgi/ecss.ini
COPY . $APP_DIR

# Set up folder for optional SQLite use
RUN mkdir /var/opt/ecss \
	&& chown nginx:nginx /var/opt/ecss
RUN chmod u+x docker-run.sh

CMD ["./docker-run.sh"]
