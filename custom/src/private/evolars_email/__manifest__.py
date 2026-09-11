# -*- coding: utf-8 -*-
{
    'name': 'E-mail',
    'version': '17.0.1.0.0',
    'category': 'Productivity/Mail',
    'summary': 'Hub Corporativo e Genérico de E-mails com Resend (Inbound Webhook, Outbound, Caixas Institucionais e Portal)',
    'description': """
Módulo Odoo Genérico e Reutilizável para Gestão de E-mails com Resend:
======================================================================
* Envio de E-mails via Resend API com rastreamento transacional e suporte a anexos.
* Ingestão Inbound via Webhook direto (/api/webhooks/resend) com validação por domínio (ADR-015).
* Garantia de Idempotência estrita por resend_email_id.
* Provisionamento automático de e-mails @dominio e caixas postais para contatos.
* Painel Administrativo de Caixas Postais, Aliases e Lixeira.
* Portal web do Aluno / Família para leitura, resposta e envio de e-mails institucionais.
    """,
    'author': 'Evolars Ltda',
    'website': 'https://evolars.com.br',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'views/email_mailbox_views.xml',
        'views/email_alias_views.xml',
        'views/email_message_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/email_composer_views.xml',
        'views/portal_templates.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
