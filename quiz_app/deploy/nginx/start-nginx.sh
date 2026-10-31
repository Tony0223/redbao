#!/bin/sh
set -eu

CERTIFICATE_PATH="/etc/letsencrypt/live/${API_DOMAIN}/fullchain.pem"
HTTP_TEMPLATE="/opt/quiz-nginx/quiz-api-http.conf.template"
HTTPS_TEMPLATE="/opt/quiz-nginx/quiz-api-https.conf.template"
NGINX_CONFIG="/etc/nginx/conf.d/default.conf"

certificate_hash() {
    if [ -f "$CERTIFICATE_PATH" ]; then
        cksum "$CERTIFICATE_PATH" | awk '{print $1 ":" $2}'
    else
        echo "missing"
    fi
}

render_config() {
    if [ -f "$CERTIFICATE_PATH" ]; then
        template="$HTTPS_TEMPLATE"
        echo "HTTPS certificate found; rendering HTTPS configuration."
    else
        template="$HTTP_TEMPLATE"
        echo "HTTPS certificate not found; rendering HTTP configuration."
    fi

    envsubst '${API_DOMAIN}' < "$template" > "$NGINX_CONFIG"
}

render_config
last_certificate_hash="$(certificate_hash)"

(
    while :; do
        sleep 60
        current_certificate_hash="$(certificate_hash)"

        if [ "$current_certificate_hash" != "$last_certificate_hash" ]; then
            echo "Certificate change detected; reloading Nginx."
            render_config
            if nginx -t; then
                nginx -s reload
                last_certificate_hash="$current_certificate_hash"
            fi
        fi
    done
) &

exec nginx -g 'daemon off;'
