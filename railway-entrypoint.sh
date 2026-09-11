#!/bin/sh
set -eu

mkdir -p /var/lib/odoo/filestore /var/lib/odoo/sessions
chown -R 1000:1000 /var/lib/odoo || true
chmod -R 775 /var/lib/odoo || true

exec setpriv \
  --reuid=1000 \
  --regid=1000 \
  --init-groups \
  /opt/odoo/common/entrypoint "$@" 2>&1
