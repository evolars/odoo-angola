# -*- coding: utf-8 -*-
import re
import unicodedata
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    mailbox_ids = fields.One2many(
        'evolars.email.mailbox',
        'partner_id',
        string='Caixas Postais Institucionais'
    )
    email_message_count = fields.Integer(
        string='Mensagens de E-mail',
        compute='_compute_email_message_count'
    )

    def _compute_email_message_count(self):
        for partner in self:
            partner.email_message_count = self.env['evolars.email.message'].sudo().search_count([
                '|', ('partner_id', '=', partner.id),
                '|', ('from_address', 'ilike', partner.email or '___none___'),
                ('to_addresses', 'ilike', partner.email or '___none___')
            ])

    @api.model
    def _slugify_for_email(self, name):
        """Converte o nome em um slug limpo para endereço de e-mail (ex: João da Silva -> joao.silva)."""
        if not name:
            return "contato"
        # Remove acentos
        nfkd = unicodedata.normalize('NFKD', name)
        clean_text = "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()
        # Divide por palavras e remove conectivos em português
        words = re.findall(r'[a-z0-9]+', clean_text)
        stopwords = {'da', 'de', 'do', 'das', 'dos', 'e', 'em', 'para', 'com'}
        filtered = [w for w in words if w not in stopwords]
        
        if not filtered:
            return "usuario"
        if len(filtered) == 1:
            return filtered[0]
        # Pega primeiro e último nome
        return f"{filtered[0]}.{filtered[-1]}"

    @api.model
    def _generate_unique_institutional_email(self, name, domain):
        """Gera um e-mail único no domínio informado com resolução de homônimos."""
        base_slug = self._slugify_for_email(name)
        candidate = f"{base_slug}@{domain}".lower()

        existing = self.sudo().search_count([('email', '=ilike', candidate)])
        existing_mb = self.env['evolars.email.mailbox'].sudo().search_count([('email_address', '=ilike', candidate)])

        if existing == 0 and existing_mb == 0:
            return candidate

        # Se já existe, adiciona sufixo numérico
        counter = 2
        while True:
            candidate = f"{base_slug}{counter}@{domain}".lower()
            if self.sudo().search_count([('email', '=ilike', candidate)]) == 0 and \
               self.env['evolars.email.mailbox'].sudo().search_count([('email_address', '=ilike', candidate)]) == 0:
                return candidate
            counter += 1

    @api.model_create_multi
    def create(self, vals_list):
        auto_create = self.env['ir.config_parameter'].sudo().get_param('resend.auto_create_partner_email', 'True') == 'True'
        domain = self.env['evolars.resend.service']._get_system_domain()

        for vals in vals_list:
            # Se não tiver e-mail informado e auto_create estiver ativo, gera o e-mail @dominio
            if auto_create and not vals.get('email') and vals.get('name'):
                vals['email'] = self._generate_unique_institutional_email(vals['name'], domain)

        partners = super().create(vals_list)

        # Sincroniza criação de Mailbox para cada parceiro criado
        for partner in partners:
            if partner.email and '@' in partner.email and auto_create:
                partner_domain = partner.email.split('@')[1].strip().lower()
                if partner_domain == domain:
                    # Cria Mailbox se não existir
                    existing_mb = self.env['evolars.email.mailbox'].sudo().search([
                        ('email_address', '=', partner.email.lower())
                    ], limit=1)
                    if not existing_mb:
                        self.env['evolars.email.mailbox'].sudo().create({
                            'name': partner.name,
                            'email_address': partner.email.lower(),
                            'partner_id': partner.id,
                            'user_ids': [(6, 0, partner.user_ids.ids)] if partner.user_ids else False,
                            'is_shared': False,
                        })

        return partners

    def write(self, vals):
        res = super().write(vals)
        auto_create = self.env['ir.config_parameter'].sudo().get_param('resend.auto_create_partner_email', 'True') == 'True'
        domain = self.env['evolars.resend.service']._get_system_domain()

        if auto_create and ('email' in vals or 'user_ids' in vals):
            for partner in self:
                if partner.email and '@' in partner.email:
                    p_domain = partner.email.split('@')[1].strip().lower()
                    if p_domain == domain:
                        mb = self.env['evolars.email.mailbox'].sudo().search([
                            '|', ('partner_id', '=', partner.id),
                            ('email_address', '=ilike', partner.email.strip().lower())
                        ], limit=1)
                        if mb:
                            vals_to_write = {
                                'email_address': partner.email.lower(),
                                'name': partner.name,
                            }
                            if not mb.partner_id:
                                vals_to_write['partner_id'] = partner.id
                            if partner.user_ids:
                                vals_to_write['user_ids'] = [(6, 0, partner.user_ids.ids)]
                            mb.write(vals_to_write)
                        else:
                            self.env['evolars.email.mailbox'].sudo().create({
                                'name': partner.name,
                                'email_address': partner.email.lower(),
                                'partner_id': partner.id,
                                'user_ids': [(6, 0, partner.user_ids.ids)] if partner.user_ids else False,
                                'is_shared': False,
                            })
        return res

    def action_view_email_messages(self):
        self.ensure_one()
        return {
            'name': _('E-mails — %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'evolars.email.message',
            'view_mode': 'tree,form',
            'domain': [
                '|', ('partner_id', '=', self.id),
                '|', ('from_address', 'ilike', self.email or '___none___'),
                ('to_addresses', 'ilike', self.email or '___none___')
            ],
            'context': {
                'default_partner_id': self.id,
                'default_to_addresses': self.email,
            },
        }
