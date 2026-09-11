# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import controllers


def post_init_hook(env):
    icp = env['ir.config_parameter'].sudo()
    if not icp.get_param('resend.domain'):
        icp.set_param('resend.domain', 'evolars.com.br')
    if not icp.get_param('resend.default_from'):
        icp.set_param('resend.default_from', 'Evolars Angola <angola@evolars.com.br>')
    if not icp.get_param('resend.auto_create_partner_email'):
        icp.set_param('resend.auto_create_partner_email', 'True')
    env['evolars.email.mailbox'].sudo().action_provision_all_mailboxes()
