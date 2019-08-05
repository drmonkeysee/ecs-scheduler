#!/bin/sh

mv /etc/nginx/conf.d/default.conf /etc/nginx/default.conf.bak
exec nginx -g 'daemon off;'
