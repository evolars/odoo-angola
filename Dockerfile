ARG ODOO_VERSION=17.0
FROM ghcr.io/tecnativa/doodba:${ODOO_VERSION}-onbuild

USER root
ENV GH_TOKEN=""
ENV INITIAL_LANG=pt_AO
COPY scripts/initialize-odoo-base.sh /usr/local/bin/initialize-odoo-base
COPY railway-entrypoint.sh /usr/local/bin/railway-entrypoint
RUN chmod 0755 /usr/local/bin/initialize-odoo-base /usr/local/bin/railway-entrypoint
ENTRYPOINT ["/usr/local/bin/railway-entrypoint"]
CMD ["/usr/local/bin/odoo"]
