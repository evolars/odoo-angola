# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class EmailMessage(models.Model):
    _name = 'evolars.email.message'
    _description = 'Mensagem de E-mail (Resend)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Assunto', required=True, default='(Sem Assunto)', tracking=True)
    from_address = fields.Char(string='De (Remetente)', required=True, index=True, tracking=True)
    to_addresses = fields.Char(string='Para (Destinatários)', required=True, index=True, tracking=True)
    cc_addresses = fields.Char(string='Cc (Cópia)')
    bcc_addresses = fields.Char(string='Cco (Cópia Oculta)')
    reply_to = fields.Char(string='Responder Para')

    mailbox_id = fields.Many2one(
        'evolars.email.mailbox',
        string='Caixa Postal',
        index=True,
        ondelete='set null',
        tracking=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contato Associado',
        index=True,
        ondelete='set null',
        tracking=True
    )
    user_ids = fields.Many2many(
        'res.users',
        'evolars_email_message_user_rel',
        'message_id',
        'user_id',
        string='Usuários com Acesso'
    )

    direction = fields.Selection([
        ('inbound', 'Recebido'),
        ('outbound', 'Enviado'),
    ], string='Direção', default='inbound', required=True, index=True)

    state = fields.Selection([
        ('draft', 'Rascunho'),
        ('received', 'Recebido'),
        ('sent', 'Enviado'),
        ('failed', 'Falha no Envio'),
        ('trash', 'Lixeira'),
        ('archived', 'Arquivado'),
    ], string='Estado', default='received', required=True, index=True, tracking=True)

    is_read = fields.Boolean(string='Lido', default=False, index=True)
    is_starred = fields.Boolean(string='Favorito / Destaque', default=False, index=True)
    date = fields.Datetime(string='Data/Hora', default=fields.Datetime.now, required=True, index=True)

    body_html = fields.Html(string='Conteúdo HTML', sanitize=False)
    body_text = fields.Text(string='Conteúdo em Texto')

    resend_email_id = fields.Char(
        string='Resend Email ID',
        index=True,
        copy=False,
        help='Identificador único do e-mail na infraestrutura do Resend'
    )
    error_message = fields.Text(string='Detalhes do Erro')
    raw_payload = fields.Text(string='Payload Bruto (Auditoria)', readonly=True)

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'evolars_email_message_attachment_rel',
        'message_id',
        'attachment_id',
        string='Anexos'
    )

    _sql_constraints = [
        ('resend_email_id_uniq', 'unique(resend_email_id)', 'Este e-mail do Resend já foi processado anteriormente (Idempotência garantida)!')
    ]

    def action_mark_read(self):
        self.write({'is_read': True})

    def action_mark_unread(self):
        self.write({'is_read': False})

    def action_toggle_star(self):
        for rec in self:
            rec.is_starred = not rec.is_starred

    def action_move_trash(self):
        self.write({'state': 'trash'})

    def action_restore(self):
        for rec in self:
            rec.state = 'received' if rec.direction == 'inbound' else 'sent'

    def action_reply(self):
        self.ensure_one()
        # Determina remetente da resposta
        from_mb = self.mailbox_id
        if not from_mb:
            from_mb = self.env['evolars.email.mailbox'].search([
                ('email_address', '=', self.env['evolars.resend.service']._get_system_domain())
            ], limit=1)

        reply_subject = self.name
        if not reply_subject.lower().startswith('re:'):
            reply_subject = f"Re: {reply_subject}"

        return {
            'name': _('Responder E-mail'),
            'type': 'ir.actions.act_window',
            'res_model': 'evolars.email.composer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_from_mailbox_id': from_mb.id if from_mb else False,
                'default_to_addresses': self.from_address,
                'default_subject': reply_subject,
                'default_reply_to_message_id': self.id,
                'default_body_html': f"<br/><br/><blockquote>--- Em {self.date}, {self.from_address} escreveu: ---<br/>{self.body_html or self.body_text or ''}</blockquote>",
            }
        }
