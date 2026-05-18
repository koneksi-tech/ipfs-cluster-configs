#!/bin/bash
# NHN Grafana behind nginx TLS: nhn-grafana.co.kr -> http://127.0.0.1:3000
#
# Default cert paths: invoking user's ~/ssl/fullchain.pem and ~/ssl/koneksi.co.kr.key
# (e.g. ubuntu: /home/ubuntu/ssl/... when you run sudo bash this script).
# Override: SSL_CERT=... SSL_KEY=... DOMAIN=... sudo ./setup-nginx-grafana-nhn-ssl.sh
#
# Before: DNS A record for DOMAIN must point at this server (e.g. 133.186.241.75).
# Cert SAN must include nhn-grafana.co.kr (or use a wildcard).
#
# Run: sudo bash setup-nginx-grafana-nhn-ssl.sh

set -euo pipefail

SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  exec sudo -E /bin/bash "$SCRIPT_ABS" "$@"
fi

if [[ -n "${SUDO_USER:-}" ]]; then
  INVOKER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
  INVOKER_HOME="${HOME:-/root}"
fi

DOMAIN="${DOMAIN:-nhn-grafana.co.kr}"
SSL_CERT="${SSL_CERT:-${INVOKER_HOME}/ssl/fullchain.pem}"
SSL_KEY="${SSL_KEY:-${INVOKER_HOME}/ssl/koneksi.co.kr.key}"
GRAFANA_UPSTREAM="${GRAFANA_UPSTREAM:-127.0.0.1:3000}"

echo "==> Cert paths"
[[ -f "$SSL_CERT" ]] || { echo "Missing cert: $SSL_CERT" >&2; exit 1; }
[[ -f "$SSL_KEY" ]] || { echo "Missing key: $SSL_KEY" >&2; exit 1; }

chown root:root "$SSL_CERT"
chmod 644 "$SSL_CERT"
chown root:root "$SSL_KEY"
chmod 600 "$SSL_KEY"
echo "    $SSL_CERT -> 644 root:root"
echo "    $SSL_KEY -> 600 root:root"

echo "==> nginx"
apt-get update -y
apt-get install -y --no-install-recommends nginx

# map must live in http {} — conf.d is included there on Ubuntu/Debian
install -d -m 0755 /etc/nginx/conf.d
cat >/etc/nginx/conf.d/00-grafana-websocket-map.conf <<'MAP'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
MAP

SITE="/etc/nginx/sites-available/${DOMAIN}"
cat >"$SITE" <<NGX
# Grafana reverse proxy - ${DOMAIN}
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    # http2 on same line as listen (nginx 1.18 / Ubuntu 20.04). Newer nginx also accepts this.
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     ${SSL_CERT};
    ssl_certificate_key ${SSL_KEY};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    # Grafana UI + live features (websockets)
    location / {
        proxy_pass http://${GRAFANA_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
NGX

ln -sfn "$SITE" "/etc/nginx/sites-enabled/${DOMAIN}"
# default site often steals :80 — disable if present
if [[ -L /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl enable nginx
systemctl reload nginx

echo "==> Grafana public URL (fixes 'failed to load application files' behind proxy)"
GRAFANA_ENV=/etc/default/grafana-server
touch "$GRAFANA_ENV"
sed -i '/^GF_SERVER_ROOT_URL=/d;/^GF_SERVER_DOMAIN=/d;/^GF_SERVER_SERVE_FROM_SUB_PATH=/d' "$GRAFANA_ENV" 2>/dev/null || true
{
  echo ""
  echo "# Added by setup-nginx-grafana-nhn-ssl.sh - public URL is https through nginx"
  echo "GF_SERVER_ROOT_URL=https://${DOMAIN}/"
  echo "GF_SERVER_DOMAIN=${DOMAIN}"
  echo "GF_SERVER_SERVE_FROM_SUB_PATH=false"
} >>"$GRAFANA_ENV"

systemctl restart grafana-server

echo ""
echo "Done."
echo "  https://${DOMAIN}/  (after DNS points here)"
echo "  Grafana still on http://127.0.0.1:3000 locally — close port 3000 on the firewall from the internet if possible."
echo "  If the UI still breaks, hard-refresh the browser or try a private window."
