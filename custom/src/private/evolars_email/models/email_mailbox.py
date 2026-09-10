# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EmailMailbox(models.Model):
    _name = 'evolars.email.mailbox'
    _description = 'Caixa Postal Institucional'
    _order = 'is_shared desc, name asc'

    name = fields.Char(string='Nome da Caixa', required=True)
    email_address = fields.Char(string='Endereço de E-mail', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Contato Titular', ondelete='set null')
    user_ids = fields.Many2many(
        'res.users',
        'evolars_email_mailbox_user_rel',
        'mailbox_id',
        'user_id',
        string='Usuários Autorizados'
    )
    is_shared = fields.Boolean(
        string='Caixa Compartilhada / Equipe',
        default=False,
        help='Indica se a caixa é de uso departamental/equipe (ex: secretaria, financeiro)'
    )
    active = fields.Boolean(string='Ativa', default=True)
    color = fields.Integer(string='Índice de Cor', default=0)
    
    alias_ids = fields.One2many(
        'evolars.email.alias',
        'mailbox_id',
        string='Aliases Redirecionados'
    )
    message_ids = fields.One2many(
        'evolars.email.message',
        'mailbox_id',
        string='Mensagens'
    )

    unread_count = fields.Integer(
        string='Não Lidas',
        compute='_compute_message_counts',
        store=False
    )
    total_count = fields.Integer(
        string='Total de Mensagens',
        compute='_compute_message_counts',
        store=False
    )

    _sql_constraints = [
        ('email_address_uniq', 'unique(email_address)', 'Já existe uma caixa postal cadastrada com este endereço de e-mail!')
    ]

    @api.constrains('email_address')
    def _check_email_address(self):
        for rec in self:
            if not rec.email_address or '@' not in rec.email_address:
                raise ValidationError(_("O endereço de e-mail informado (%s) é inválido.") % rec.email_address)

    @api.onchange('email_address')
    def _onchange_email_address(self):
        if self.email_address:
            self.email_address = self.email_address.strip().lower()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('email_address'):
                vals['email_address'] = vals['email_address'].strip().lower()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('email_address'):
            vals['email_address'] = vals['email_address'].strip().lower()
        return super().write(vals)

    def _compute_message_counts(self):
        for rec in self:
            rec.total_count = len(rec.message_ids)
            rec.unread_count = len(rec.message_ids.filtered(lambda m: not m.is_read and m.state != 'trash'))

    def action_view_messages(self):
        self.ensure_one()
        return {
            'name': _('Mensagens — %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'evolars.email.message',
            'view_mode': 'tree,form',
            'domain': [('mailbox_id', '=', self.id)],
            'context': {'default_mailbox_id': self.id},
        }

    @api.model
    def action_provision_all_mailboxes(self):
        """
        Provisiona e sincroniza automaticamente as caixas postais para todos os
        usuários e contatos (professores, pais, alunos, equipe) no domínio do sistema.
        """
        domain = self.env['evolars.resend.service'].sudo()._get_system_domain()
        if not domain:
            domain = 'c-edl.com'

        # 1. Caixas Compartilhadas / Departamentais Padrão
        shared_mailboxes = [
            {'name': 'Secretaria Escolar', 'email': f'secretaria@{domain}'},
            {'name': 'Coordenação Pedagógica', 'email': f'coordenacao@{domain}'},
            {'name': 'Diretoria Geral', 'email': f'diretoria@{domain}'},
            {'name': 'Financeiro & Mensalidades', 'email': f'financeiro@{domain}'},
            {'name': 'Ouvidoria & Acolhimento Anti-Bullying', 'email': f'ouvidoria@{domain}'},
        ]
        for sm in shared_mailboxes:
            mb = self.search([('email_address', '=ilike', sm['email'])], limit=1)
            if not mb:
                self.create({
                    'name': sm['name'],
                    'email_address': sm['email'],
                    'is_shared': True,
                    'active': True,
                })

        # 2. Provisionamento para Usuários do Sistema (res.users)
        users = self.env['res.users'].sudo().search([('active', '=', True)])
        for user in users:
            partner = user.partner_id
            if not partner:
                continue

            # Se o login já é @dominio, prioriza o login
            if user.login and '@' in user.login and user.login.split('@')[1].strip().lower() == domain:
                target_email = user.login.strip().lower()
            elif partner.email and '@' in partner.email and partner.email.split('@')[1].strip().lower() == domain:
                target_email = partner.email.strip().lower()
            else:
                target_email = self.env['res.partner'].sudo()._generate_unique_institutional_email(partner.name or user.name, domain)
                partner.sudo().write({'email': target_email})

            mb = self.search([
                '|', ('partner_id', '=', partner.id),
                ('email_address', '=ilike', target_email)
            ], limit=1)
            if mb:
                vals_to_write = {}
                if not mb.partner_id:
                    vals_to_write['partner_id'] = partner.id
                if user.id not in mb.user_ids.ids:
                    vals_to_write['user_ids'] = [(4, user.id)]
                if mb.email_address != target_email:
                    vals_to_write['email_address'] = target_email
                if vals_to_write:
                    mb.sudo().write(vals_to_write)
            else:
                self.create({
                    'name': partner.name or user.name,
                    'email_address': target_email,
                    'partner_id': partner.id,
                    'user_ids': [(4, user.id)],
                    'is_shared': False,
                    'active': True,
                })

        # 3. Provisionamento para Contatos Ativos (Professores, Responsáveis, Alunos)
        partners = self.env['res.partner'].sudo().search([
            ('active', '=', True),
            ('is_company', '=', False),
        ])
        for partner in partners:
            if not partner.email or '@' not in partner.email or partner.email.split('@')[1].strip().lower() != domain:
                new_email = self.env['res.partner'].sudo()._generate_unique_institutional_email(partner.name, domain)
                partner.sudo().write({'email': new_email})
                target_email = new_email
            else:
                target_email = partner.email.strip().lower()

            mb = self.search([
                '|', ('partner_id', '=', partner.id),
                ('email_address', '=ilike', target_email)
            ], limit=1)
            if not mb:
                self.create({
                    'name': partner.name,
                    'email_address': target_email,
                    'partner_id': partner.id,
                    'user_ids': [(6, 0, partner.user_ids.ids)] if partner.user_ids else False,
                    'is_shared': False,
                    'active': True,
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronização Concluída'),
                'message': _('Todas as caixas de e-mail institucionais foram provisionadas com sucesso!'),
                'type': 'success',
                'sticky': False,
            }
        }


class EmailAlias(models.Model):
    _name = 'evolars.email.alias'
    _description = 'Alias de Roteamento de E-mail'
    _order = 'alias_address asc'

    name = fields.Char(string='Identificação do Alias', required=True)
    alias_address = fields.Char(string='Endereço do Alias', required=True, index=True)
    mailbox_id = fields.Many2one(
        'evolars.email.mailbox',
        string='Caixa Postal de Destino',
        required=True,
        ondelete='cascade'
    )
    active = fields.Boolean(string='Ativo', default=True)

    _sql_constraints = [
        ('alias_address_uniq', 'unique(alias_address)', 'Já existe um alias cadastrado com este endereço de e-mail!')
    ]

    @api.onchange('alias_address')
    def _onchange_alias_address(self):
        if self.alias_address:
            self.alias_address = self.alias_address.strip().lower()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('alias_address'):
                vals['alias_address'] = vals['alias_address'].strip().lower()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('alias_address'):
            vals['alias_address'] = vals['alias_address'].strip().lower()
        return super().write(vals)
