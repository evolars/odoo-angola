#!/bin/sh
set -eu

: "${PGDATABASE:?PGDATABASE is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

export ODOO_BOOTSTRAP_MODULES="base,remove_odoo_enterprise,disable_odoo_online,web_responsive,website,website_slides,portal,evolars_email,evolars_angola_theme"
export ODOO_UPGRADE_MODULES="evolars_email,evolars_angola_theme"

echo "[initialize-odoo-base] Verificando e garantindo role '$PGUSER', banco '$PGDATABASE' e permissões..."
python3 - <<'PY'
import os
import sys
import time
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

host = os.environ["PGHOST"]
port = int(os.environ["PGPORT"])
admin_user = os.environ.get("ADMIN_USER", "postgres")
admin_password = os.environ.get("ADMIN_PASSWORD", os.environ["PGPASSWORD"])
app_user = os.environ["PGUSER"]
app_password = os.environ["PGPASSWORD"]
target_db = os.environ["PGDATABASE"]

# 1. Aguardar Postgres estar online
connected = False
for attempt in range(1, 31):
    for default_db in ("postgres", "railway"):
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=admin_user, password=admin_password, dbname=default_db, connect_timeout=3
            )
            conn.close()
            connected = True
            admin_db = default_db
            break
        except Exception:
            continue
    if connected:
        break
    time.sleep(1)

if not connected:
    print("[initialize-odoo-base] Erro: Timeout aguardando PostgreSQL.", file=sys.stderr)
    sys.exit(1)

# 2. Conectar como admin e garantir role app_user
conn = psycopg2.connect(
    host=host, port=port, user=admin_user, password=admin_password, dbname=admin_db
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
if not cur.fetchone():
    print(f"[initialize-odoo-base] Criando role '{app_user}'...")
    cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {} SUPERUSER CREATEDB;").format(
        sql.Identifier(app_user),
        sql.Literal(app_password)
    ))
else:
    cur.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {} SUPERUSER CREATEDB;").format(
        sql.Identifier(app_user),
        sql.Literal(app_password)
    ))

# 3. Garantir target_db com owner app_user
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
if not cur.fetchone():
    print(f"[initialize-odoo-base] Criando banco de dados '{target_db}' com owner '{app_user}'...")
    cur.execute(sql.SQL("CREATE DATABASE {} OWNER {};").format(
        sql.Identifier(target_db),
        sql.Identifier(app_user)
    ))
else:
    cur.execute(sql.SQL("ALTER DATABASE {} OWNER TO {};").format(
        sql.Identifier(target_db),
        sql.Identifier(app_user)
    ))

cur.close()
conn.close()

# 4. Conectar no target_db como admin e garantir schema public owner e grants
conn = psycopg2.connect(
    host=host, port=port, user=admin_user, password=admin_password, dbname=target_db
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute(sql.SQL("ALTER SCHEMA public OWNER TO {};").format(sql.Identifier(app_user)))
cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {};").format(sql.Identifier(app_user)))
cur.close()
conn.close()

print(f"[initialize-odoo-base] Role '{app_user}' e banco '{target_db}' prontos.")
PY

configure_settings() {
  /opt/odoo/common/entrypoint /usr/local/bin/odoo shell --database "$PGDATABASE" <<'PY'
import os
import base64

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

company = env.ref("base.main_company", raise_if_not_found=False)
if company:
    company.name = "Evolars Angola"
    company.website = "https://angola.evolars.com.br"
    company.email = "angola@evolars.com.br"
    logo_path = "/opt/odoo/custom/src/private/evolars_angola_theme/static/src/img/evolars_logo_horizontal_white.png"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            company.logo = base64.b64encode(f.read())

website = env["website"].search([], limit=1)
if website:
    website.name = "Evolars Angola"
    website.domain = "https://angola.evolars.com.br"
    logo_path = "/opt/odoo/custom/src/private/evolars_angola_theme/static/src/img/evolars_logo_horizontal_white.png"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            website.logo = base64.b64encode(f.read())

env["ir.config_parameter"].set_param("web.base.url", "https://angola.evolars.com.br")
env["ir.config_parameter"].set_param("web.base.url.freeze", "True")

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
