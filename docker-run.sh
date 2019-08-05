#!/bin/sh

mv /etc/nginx/conf.d/default.conf /etc/nginx/default.conf.bak
uwsgi /etc/uwsgi/ecss.ini &
exec nginx -g 'daemon off;'
