# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError


class EvolarsEmailPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'email_count' in counters:
            partner = request.env.user.partner_id
            # Busca mensagens onde o parceiro ou seus filhos sejam remetente/destinatário
            dependent_ids = [partner.id]
            if hasattr(partner, 'child_ids') and partner.child_ids:
                dependent_ids.extend(partner.child_ids.ids)

            emails_to_check = [partner.email] if partner.email else []
            for d in partner.child_ids:
                if d.email:
                    emails_to_check.append(d.email)

            domain = [
                '|', ('partner_id', 'in', dependent_ids),
                '|', ('from_address', 'in', emails_to_check),
                ('to_addresses', 'ilike', partner.email or '___none___')
            ]
            values['email_count'] = request.env['evolars.email.message'].sudo().search_count(domain)
        return values

    def _get_portal_emails_domain(self):
        partner = request.env.user.partner_id
        dependent_ids = [partner.id]
        if hasattr(partner, 'child_ids') and partner.child_ids:
            dependent_ids.extend(partner.child_ids.ids)

        emails_to_check = [partner.email] if partner.email else []
        for d in partner.child_ids:
            if d.email:
                emails_to_check.append(d.email)

        return [
            ('state', '!=', 'trash'),
            '|', ('partner_id', 'in', dependent_ids),
            '|', ('from_address', 'in', emails_to_check),
            ('to_addresses', 'ilike', partner.email or '___none___')
        ]

    @http.route(['/my/emails', '/my/emails/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_emails(self, page=1, sortby=None, filterby=None, search=None, search_in='content', **kw):
        values = self._prepare_portal_layout_values()
        EmailMessage = request.env['evolars.email.message'].sudo()

        domain = self._get_portal_emails_domain()

        if search and search_in:
            if search_in in ('all', 'content'):
                domain += ['|', ('name', 'ilike', search), ('body_text', 'ilike', search)]
            elif search_in == 'sender':
                domain += [('from_address', 'ilike', search)]
            elif search_in == 'subject':
                domain += [('name', 'ilike', search)]

        if filterby == 'inbound':
            domain += [('direction', '=', 'inbound')]
        elif filterby == 'outbound':
            domain += [('direction', '=', 'outbound')]
        elif filterby == 'unread':
            domain += [('is_read', '=', False), ('direction', '=', 'inbound')]

        email_count = EmailMessage.search_count(domain)
        pager = portal_pager(
            url="/my/emails",
            url_args={'sortby': sortby, 'filterby': filterby, 'search_in': search_in, 'search': search},
            total=email_count,
            page=page,
            step=15
        )

        messages = EmailMessage.search(domain, order="date desc", limit=15, offset=pager['offset'])

        partner = request.env.user.partner_id
        # Mailbox do usuário logado
        my_mailbox = request.env['evolars.email.mailbox'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        values.update({
            'messages': messages,
            'page_name': 'email_inbox',
            'pager': pager,
            'default_url': '/my/emails',
            'search': search,
            'search_in': search_in,
            'sortby': sortby,
            'filterby': filterby,
            'my_mailbox': my_mailbox,
            'partner': partner,
        })
        return request.render("evolars_email.portal_my_emails_list", values)

    @http.route(['/my/emails/<int:message_id>'], type='http', auth='user', website=True)
    def portal_my_email_detail(self, message_id, **kw):
        EmailMessage = request.env['evolars.email.message'].sudo()
        domain = self._get_portal_emails_domain() + [('id', '=', message_id)]
        msg = EmailMessage.search(domain, limit=1)
        if not msg:
            raise AccessError(_("Mensagem não encontrada ou você não tem permissão para acessá-la."))

        # Marca como lida
        if not msg.is_read and msg.direction == 'inbound':
            msg.sudo().write({'is_read': True})

        values = {
            'message': msg,
            'page_name': 'email_detail',
        }
        return request.render("evolars_email.portal_my_email_detail", values)

    @http.route(['/my/emails/compose'], type='http', auth='user', website=True)
    def portal_my_email_compose(self, reply_to_id=None, **kw):
        partner = request.env.user.partner_id
        domain = request.env['evolars.resend.service'].sudo()._get_system_domain()
        
        # Obtém mailbox do usuário logado
        my_mailbox = request.env['evolars.email.mailbox'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        reply_message = None
        default_subject = ''
        default_to = f"secretaria@{domain}"
        default_body = ''

        if reply_to_id:
            reply_domain = self._get_portal_emails_domain() + [('id', '=', int(reply_to_id))]
            reply_message = request.env['evolars.email.message'].sudo().search(reply_domain, limit=1)
            if reply_message:
                default_to = reply_message.from_address
                default_subject = f"Re: {reply_message.name}" if not reply_message.name.startswith('Re:') else reply_message.name
                default_body = f"\n\n--- Em resposta à mensagem de {reply_message.from_address} em {reply_message.date} ---"

        values = {
            'partner': partner,
            'my_mailbox': my_mailbox,
            'default_from': my_mailbox.email_address if my_mailbox else (partner.email or f"{partner.id}@{domain}"),
            'default_to': default_to,
            'default_subject': default_subject,
            'default_body': default_body,
            'reply_message': reply_message,
            'page_name': 'email_compose',
        }
        return request.render("evolars_email.portal_my_email_compose", values)

    @http.route(['/my/emails/submit'], type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_my_email_submit(self, **post):
        partner = request.env.user.partner_id
        domain = request.env['evolars.resend.service'].sudo()._get_system_domain()

        to_addr = post.get('to_address', '').strip()
        subject = post.get('subject', '').strip() or '(Sem Assunto)'
        body = post.get('body', '').strip()

        # Remetente
        my_mailbox = request.env['evolars.email.mailbox'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)
        from_addr = my_mailbox.email_address if my_mailbox else (partner.email or f"{partner.id}@{domain}")
        from_formatted = f"{partner.name} <{from_addr}>"

        # Dispara via Resend
        resend_service = request.env['evolars.resend.service'].sudo()
        res = resend_service.send_email(
            from_addr=from_formatted,
            to_addrs=[to_addr],
            subject=subject,
            body_html=f"<p>{body.replace(chr(10), '<br/>')}</p>",
            body_text=body
        )

        state = 'sent' if res.get('success') else 'failed'
        error_msg = res.get('error') if not res.get('success') else False
        resend_id = res.get('id')

        # Persiste mensagem
        msg = request.env['evolars.email.message'].sudo().create({
            'name': subject,
            'from_address': from_addr,
            'to_addresses': to_addr,
            'mailbox_id': my_mailbox.id if my_mailbox else False,
            'partner_id': partner.id,
            'direction': 'outbound',
            'state': state,
            'is_read': True,
            'body_html': f"<p>{body.replace(chr(10), '<br/>')}</p>",
            'body_text': body,
            'resend_email_id': resend_id or False,
            'error_message': error_msg,
        })

        return request.redirect('/my/emails')
