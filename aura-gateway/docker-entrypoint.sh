#!/bin/sh
set -e

envsubst '${SERVER_NAME} ${SSL_CERT_PATH} ${SSL_KEY_PATH} ${AUTH_RATE_LIMIT} ${API_RATE_LIMIT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"
