#!/bin/sh

if [ -f /etc/nginx/conf.d/default.conf ] ; then
	mv /etc/nginx/conf.d/default.conf /etc/nginx/default.conf.bak
fi
uwsgi /etc/uwsgi/ecss.ini &
exec nginx -g 'daemon off;'
