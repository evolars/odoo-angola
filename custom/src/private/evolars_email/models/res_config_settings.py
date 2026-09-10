# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    resend_api_key = fields.Char(
        string='Resend API Key',
        config_parameter='resend.api_key',
        help='Chave de API do Resend (ex: re_123456789...)'
    )
    resend_domain = fields.Char(
        string='Domínio do Sistema',
        config_parameter='resend.domain',
        default='c-edl.com',
        help='Domínio institucional para envio e validação de recebimento (ex: c-edl.com ou evolars.com.br)'
    )
    resend_default_from = fields.Char(
        string='Remetente Padrão (From)',
        config_parameter='resend.default_from',
        default='Secretaria C-EDL <secretaria@c-edl.com>',
        help='Remetente utilizado nos disparos transacionais padrão'
    )
    resend_auto_create_partner_email = fields.Boolean(
        string='Criar E-mail Institucional Automaticamente',
        config_parameter='resend.auto_create_partner_email',
        default=True,
        help='Ao criar/atualizar contatos (professores, pais e alunos), gera automaticamente o e-mail @dominio'
    )
    resend_webhook_secret = fields.Char(
        string='Webhook Secret Token',
        config_parameter='resend.webhook_secret',
        help='Token opcional para autenticação de requisições de webhook do Resend'
    )
