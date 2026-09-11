#!/bin/sh
set -eu

: "${PGDATABASE:?PGDATABASE is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

export ODOO_BOOTSTRAP_MODULES="base,remove_odoo_enterprise,disable_odoo_online,web_responsive,website,website_slides,portal,evolars_email,evolars_offline"
export ODOO_UPGRADE_MODULES="evolars_email,evolars_offline"

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

cur.execute("SELECT to_regclass('public.ir_module_module') IS NOT NULL")
if cur.fetchone()[0]:
    cur.execute("DELETE FROM ir_model_data WHERE module = 'evolars_email' AND name LIKE 'param_resend_%'")
    cur.execute("SELECT 1 FROM ir_module_module WHERE name = 'evolars_angola_theme'")
    if cur.fetchone():
        print("[initialize-odoo-base] Removendo evolars_angola_theme do banco para restaurar tema padrão...")
        cur.execute("UPDATE ir_module_module SET state = 'uninstalled' WHERE name = 'evolars_angola_theme'")
        cur.execute("DELETE FROM ir_ui_view WHERE key LIKE 'evolars_angola_theme.%'")
        cur.execute("DELETE FROM ir_asset WHERE path LIKE '%evolars_angola_theme%'")
        cur.execute("DELETE FROM ir_model_data WHERE module = 'evolars_angola_theme'")
        cur.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")

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
env["ir.config_parameter"].set_param("resend.auto_create_partner_email", "True")
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
    company.phone = "+55 11 93068-0941"
    company.mobile = "+55 11 93068-0941"
    company.vat = "62.014.621/0001-81"
    company.street = "São Paulo - SP / Atendimento Internacional Angola"
    logo_path = "/opt/odoo/custom/src/branding/evolars_logo_horizontal_dark.png"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_data = base64.b64encode(f.read())
            company.logo = logo_data
            if company.partner_id:
                company.partner_id.image_1920 = logo_data
                company.partner_id.phone = "+55 11 93068-0941"
                company.partner_id.mobile = "+55 11 93068-0941"
                company.partner_id.email = "angola@evolars.com.br"
                company.partner_id.website = "https://angola.evolars.com.br"
                company.partner_id.vat = "62.014.621/0001-81"

website = env["website"].search([], limit=1)
if website:
    website.name = "Evolars Angola"
    website.domain = "https://angola.evolars.com.br"
    website.homepage_url = "/slides"
    logo_path = "/opt/odoo/custom/src/branding/evolars_logo_horizontal_dark.png"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            website.logo = base64.b64encode(f.read())
    favicon_path = "/opt/odoo/custom/src/branding/evolars_symbol_dark.png"
    if os.path.exists(favicon_path):
        with open(favicon_path, "rb") as f:
            website.write({"favicon": base64.b64encode(f.read())})
    website.cookies_bar = False
    website.social_facebook = "https://facebook.com/evolars"
    website.social_twitter = "https://twitter.com/evolars"
    website.social_linkedin = "https://linkedin.com/company/evolars"
    website.social_github = "https://github.com/evolars"
    website.social_instagram = "https://instagram.com/evolars"

env["ir.config_parameter"].set_param("web.base.url", "https://angola.evolars.com.br")
env["ir.config_parameter"].set_param("web.base.url.freeze", "True")

# Prune any orphan attachments whose physical file is missing from filestore
filestore = f"/var/lib/odoo/filestore/{os.environ['PGDATABASE']}"
env.cr.execute("SELECT id, store_fname FROM ir_attachment WHERE store_fname IS NOT NULL")
missing_ids = [
    aid for aid, fname in env.cr.fetchall()
    if not os.path.exists(os.path.join(filestore, fname))
]
if missing_ids:
    env.cr.execute("DELETE FROM ir_attachment WHERE id = ANY(%s)", (missing_ids,))

# Guarantee course categories in website_slides
tag_group = env["slide.channel.tag.group"].search([("name", "=", "Área Técnica")], limit=1)
if not tag_group:
    tag_group = env["slide.channel.tag.group"].create({
        "name": "Área Técnica",
        "sequence": 1,
        "is_published": True,
    })
else:
    tag_group.write({
        "sequence": 1,
        "is_published": True,
    })

level_group = env["slide.channel.tag.group"].search([("name", "in", ["O Seu Nível", "Your Level"])], limit=1)
if level_group:
    level_group.write({"sequence": 10, "is_published": True})

categories = [
    ("QA & Automação de Testes", 1, 1),
    ("Engenharia de Software", 2, 2),
    ("Cibersegurança", 3, 3),
    ("Desenvolvimento Backend", 4, 4),
    ("Desenvolvimento Frontend", 5, 5),
    ("DevOps & Cloud", 6, 6),
    ("Dados & Inteligência Artificial", 7, 7),
    ("Arquitetura de Software", 8, 8),
    ("Desenvolvimento Mobile", 9, 9),
]

for name, seq, color in categories:
    tag = env["slide.channel.tag"].search([("name", "=", name), ("group_id", "=", tag_group.id)], limit=1)
    if not tag:
        env["slide.channel.tag"].create({
            "name": name,
            "group_id": tag_group.id,
            "sequence": seq,
            "color": color,
        })
    else:
        tag.write({
            "sequence": seq,
            "color": color,
        })

# Unlink previous company / website logo attachments so the new Evolars logo is immediately active
env["ir.attachment"].search([
    ("res_model", "in", ["res.company", "website"]),
    ("res_field", "in", ["logo", "favicon"])
]).unlink()

# Fix low contrast text colors in course descriptions to comply with WCAG AAA
for ch in env["slide.channel"].search([]):
    if ch.description_html and "color:" in ch.description_html:
        new_desc = (
            ch.description_html
            .replace("color: #e5e5e5", "color: #1e293b")
            .replace("color: #a3a3a3", "color: #334155")
            .replace("color: #737373", "color: #475569")
            .replace("color: #ffffff", "color: #0f172a")
        )
        if new_desc != ch.description_html:
            ch.description_html = new_desc

# Clear cached asset bundles so Odoo immediately recompiles web.assets_frontend
env["ir.attachment"].search([("url", "=like", "/web/assets/%")]).unlink()

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
    --stop-after-init 2>&1 || true
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
