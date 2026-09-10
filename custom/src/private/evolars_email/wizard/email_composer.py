# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmailComposer(models.TransientModel):
    _name = 'evolars.email.composer'
    _description = 'Assistente de Composição e Envio de E-mail (Resend)'

    @api.model
    def _default_from_mailbox(self):
        user = self.env.user
        # Tenta pegar uma mailbox pessoal do usuário ou uma compartilhada onde ele tem permissão
        mb = self.env['evolars.email.mailbox'].search([
            ('user_ids', 'in', [user.id])
        ], limit=1)
        if not mb:
            # Pega a primeira compartilhada
            mb = self.env['evolars.email.mailbox'].search([
                ('is_shared', '=', True)
            ], limit=1)
        if not mb:
            mb = self.env['evolars.email.mailbox'].search([], limit=1)
        return mb

    from_mailbox_id = fields.Many2one(
        'evolars.email.mailbox',
        string='Enviar Como (Remetente)',
        required=True,
        default=_default_from_mailbox
    )
    from_address = fields.Char(
        string='Endereço Remetente',
        related='from_mailbox_id.email_address',
        readonly=True
    )
    to_partner_ids = fields.Many2many(
        'res.partner',
        'evolars_composer_partner_rel',
        'composer_id',
        'partner_id',
        string='Contatos Destinatários'
    )
    to_addresses = fields.Char(string='Destinatários Adicionais (E-mails avulsos)')
    cc_addresses = fields.Char(string='Cc (Cópia)')
    bcc_addresses = fields.Char(string='Cco (Cópia Oculta)')

    subject = fields.Char(string='Assunto', required=True)
    body_html = fields.Html(string='Mensagem (HTML)', required=True, sanitize=False)
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'evolars_composer_attachment_rel',
        'composer_id',
        'attachment_id',
        string='Anexos'
    )
    reply_to_message_id = fields.Many2one(
        'evolars.email.message',
        string='Em Resposta A'
    )

    def action_send_email(self):
        self.ensure_one()
        all_recipients = []

        for p in self.to_partner_ids:
            if p.email:
                all_recipients.append(p.email.strip())

        if self.to_addresses:
            for addr in self.to_addresses.replace(';', ',').split(','):
                clean_addr = addr.strip()
                if clean_addr and clean_addr not in all_recipients:
                    all_recipients.append(clean_addr)

        if not all_recipients:
            raise UserError(_("Por favor, informe ao menos um destinatário válido."))

        # Formata remetente com nome da caixa
        from_formatted = f"{self.from_mailbox_id.name} <{self.from_mailbox_id.email_address}>"

        # Prepara anexos
        payload_attachments = []
        for att in self.attachment_ids:
            if att.datas:
                payload_attachments.append({
                    'filename': att.name,
                    'content': att.datas.decode('utf-8') if isinstance(att.datas, bytes) else att.datas
                })

        # Dispara via Resend API
        resend_service = self.env['evolars.resend.service']
        res = resend_service.send_email(
            from_addr=from_formatted,
            to_addrs=all_recipients,
            subject=self.subject,
            body_html=self.body_html,
            cc_addrs=self.cc_addresses,
            bcc_addrs=self.bcc_addresses,
            attachments=payload_attachments
        )

        state = 'sent' if res.get('success') else 'failed'
        error_msg = res.get('error') if not res.get('success') else False
        resend_id = res.get('id')

        # Grava a mensagem na tabela de e-mails
        msg_vals = {
            'name': self.subject,
            'from_address': self.from_mailbox_id.email_address,
            'to_addresses': ", ".join(all_recipients),
            'cc_addresses': self.cc_addresses,
            'bcc_addresses': self.bcc_addresses,
            'mailbox_id': self.from_mailbox_id.id,
            'partner_id': self.to_partner_ids[0].id if self.to_partner_ids else False,
            'direction': 'outbound',
            'state': state,
            'is_read': True,
            'date': fields.Datetime.now(),
            'body_html': self.body_html,
            'resend_email_id': resend_id or False,
            'error_message': error_msg,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)] if self.attachment_ids else False,
        }

        created_msg = self.env['evolars.email.message'].create(msg_vals)

        if not res.get('success'):
            raise UserError(_("Falha ao enviar e-mail via Resend:\n%s") % error_msg)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('E-mail Enviado!'),
                'message': _('Sua mensagem foi transmitida com sucesso através do Resend.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
