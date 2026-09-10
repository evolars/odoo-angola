#!/bin/sh
set -eu

: "${PGDATABASE:?PGDATABASE is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

export ODOO_BOOTSTRAP_MODULES="base,remove_odoo_enterprise,disable_odoo_online,web_responsive,website,website_slides,portal,evolars_email"
export ODOO_UPGRADE_MODULES="evolars_email"

echo "[initialize-odoo-base] Verificando e garantindo banco $PGDATABASE e permissões..."
python3 - <<'PY'
import os
import sys
import time
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

host = os.environ["PGHOST"]
port = int(os.environ["PGPORT"])
user = os.environ["PGUSER"]
password = os.environ["PGPASSWORD"]
target_db = os.environ["PGDATABASE"]

# 1. Aguardar Postgres estar online
connected = False
for attempt in range(1, 31):
    try:
        # Tenta conectar no banco padrão postgres ou railway
        for default_db in ("postgres", "railway"):
            try:
                conn = psycopg2.connect(
                    host=host, port=port, user=user, password=password, dbname=default_db, connect_timeout=3
                )
                conn.close()
                connected = True
                admin_db = default_db
                break
            except Exception:
                continue
        if connected:
            break
    except Exception as e:
        pass
    time.sleep(1)

if not connected:
    print("[initialize-odoo-base] Erro: Timeout aguardando PostgreSQL.", file=sys.stderr)
    sys.exit(1)

# 2. Conectar e garantir banco target_db
conn = psycopg2.connect(
    host=host, port=port, user=user, password=password, dbname=admin_db
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
if not cur.fetchone():
    print(f"[initialize-odoo-base] Criando banco de dados '{target_db}'...")
    cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(target_db)))
cur.close()
conn.close()

# 3. Conectar no target_db e garantir permissões no schema public
conn = psycopg2.connect(
    host=host, port=port, user=user, password=password, dbname=target_db
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {};").format(sql.Identifier(user)))
cur.close()
conn.close()
print(f"[initialize-odoo-base] Banco '{target_db}' pronto.")
PY

configure_settings() {
  /opt/odoo/common/entrypoint /usr/local/bin/odoo shell --database "$PGDATABASE" <<'PY'
import os

env["ir.config_parameter"].set_param("ribbon.name", False)

domain = os.environ.get("EMAIL_DOMAIN", "evolars.com.br")
default_from = os.environ.get("EMAIL_FROM", "Evolars Angola <angola@evolars.com.br>")
resend_key = os.environ.get("RESEND_API_KEY", "re_SJSa1EET_CuE1AeGwemKSMXsDUrZdzac3")

env["ir.config_parameter"].set_param("resend.domain", domain)
env["ir.config_parameter"].set_param("resend.default_from", default_from)
env["ir.config_parameter"].set_param("evolars_email.resend_api_key", resend_key)
env["ir.config_parameter"].set_param("evolars_email.default_from_email", default_from)

mail_server = env["ir.mail_server"].search([("name", "=", "Resend SMTP")], limit=1)
if not mail_server:
    env["ir.mail_server"].create({
        "name": "Resend SMTP",
        "smtp_host": "smtp.resend.com",
        "smtp_port": 465,
        "smtp_encryption": "ssl",
        "smtp_user": "resend",
        "smtp_pass": resend_key,
        "sequence": 10,
    })
else:
    mail_server.write({
        "smtp_host": "smtp.resend.com",
        "smtp_port": 465,
        "smtp_encryption": "ssl",
        "smtp_user": "resend",
        "smtp_pass": resend_key,
    })

env.cr.commit()
PY
}

/opt/odoo/common/entrypoint true

bootstrap_state="$(python3 - <<'PY'
import os
import psycopg2

connection = psycopg2.connect(
    dbname=os.environ["PGDATABASE"],
    host=os.environ["PGHOST"],
    port=os.environ["PGPORT"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
)
with connection, connection.cursor() as cursor:
    cursor.execute("SELECT to_regclass('public.ir_module_module') IS NOT NULL")
    if not cursor.fetchone()[0]:
        print("empty")
    else:
        modules = os.environ["ODOO_BOOTSTRAP_MODULES"].split(",")
        cursor.execute(
            """
            SELECT name
            FROM ir_module_module
            WHERE name = ANY(%s) AND state = 'installed'
            """,
            (modules,),
        )
        installed = {row[0] for row in cursor}
        missing = [module for module in modules if module not in installed]
        print("initialized" if not missing else ",".join(missing))
PY
)"

if [ "$bootstrap_state" = "initialized" ]; then
  echo "Odoo database is initialized; updating modules and applying settings."
  /opt/odoo/common/entrypoint \
    /usr/local/bin/odoo \
    --database "$PGDATABASE" \
    --update "$ODOO_UPGRADE_MODULES" \
    --stop-after-init || true
  configure_settings
  exit 0
fi

if [ "$bootstrap_state" != "empty" ]; then
  exec /opt/odoo/common/entrypoint \
    /usr/local/bin/odoo \
    --database "$PGDATABASE" \
    --init "$bootstrap_state" \
    --update "$ODOO_UPGRADE_MODULES" \
    --stop-after-init
fi

/opt/odoo/common/entrypoint \
  /usr/local/bin/odoo \
  --database "$PGDATABASE" \
  --init "$ODOO_BOOTSTRAP_MODULES" \
  --load-language "${INITIAL_LANG:-pt_AO}" \
  --without-demo=all \
  --stop-after-init

configure_settings
