# -*- coding: utf-8 -*-
import base64
import json
import logging
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ResendWebhookController(http.Controller):

    @http.route([
        '/api/webhooks/resend',
        '/evolars_email/webhook'
    ], type='http', auth='public', methods=['POST'], csrf=False)
    def resend_inbound_webhook(self, **kwargs):
        """
        Ingestão de e-mails via Webhook do Resend (ADR-015).
        Valida diretamente pelo domínio configurado no sistema (EMAIL_DOMAIN).
        Garante idempotência estrita através do resend_email_id.
        """
        try:
            raw_body = request.httprequest.get_data(as_text=True)
            data = {}
            if raw_body:
                try:
                    data = json.loads(raw_body)
                except Exception:
                    data = {}
            if not data:
                data = kwargs

            # Suporte a envelopamento JSON-RPC e Resend event
            if isinstance(data, dict) and 'params' in data:
                data = data['params']

            email_data = data.get('data') if isinstance(data.get('data'), dict) else data
            if not isinstance(email_data, dict):
                email_data = data

            email_id = email_data.get('email_id') or email_data.get('id')
            from_addr = email_data.get('from', '')
            to_raw = email_data.get('to', [])
            subject = email_data.get('subject', '(Sem Assunto)')
            html_body = email_data.get('html', '')
            text_body = email_data.get('text', '')

            # Normaliza destinatários em lista
            if isinstance(to_raw, str):
                to_list = [t.strip().lower() for t in to_raw.replace(';', ',').split(',') if t.strip()]
            else:
                to_list = [t.strip().lower() for t in (to_raw or []) if t.strip()]

            # Obtém domínio do sistema configurado
            system_domain = request.env['evolars.resend.service'].sudo()._get_system_domain()

            # 1. VALIDAÇÃO DIRETA DE DOMÍNIO (ADR-015)
            # Verifica se algum destinatário pertence ao domínio deste sistema
            is_for_domain = any(
                ('@' in addr and addr.split('@')[1].replace('>', '').strip() == system_domain)
                for addr in to_list
            )

            # Também checa se existe mailbox ou alias explícito no banco
            matched_mailbox = False
            for addr in to_list:
                clean_addr = addr.split('<')[-1].replace('>', '').strip().lower()
                # Checa se é um alias
                alias = request.env['evolars.email.alias'].sudo().search([
                    ('alias_address', '=', clean_addr),
                    ('active', '=', True)
                ], limit=1)
                if alias:
                    matched_mailbox = alias.mailbox_id
                    is_for_domain = True
                    break

                # Checa se é uma caixa postal direta
                mb = request.env['evolars.email.mailbox'].sudo().search([
                    ('email_address', '=', clean_addr),
                    ('active', '=', True)
                ], limit=1)
                if mb:
                    matched_mailbox = mb
                    is_for_domain = True
                    break

            if not is_for_domain:
                _logger.info("[Resend Webhook]: E-mail ignorado. Destinatário fora do domínio %s: %s", system_domain, to_list)
                return Response(json.dumps({'status': 'ignored_different_domain'}), content_type='application/json;charset=utf-8', status=200)

            # 2. IDEMPOTÊNCIA: Checa se este e-mail já foi processado
            if email_id:
                existing = request.env['evolars.email.message'].sudo().search([
                    ('resend_email_id', '=', str(email_id))
                ], limit=1)
                if existing:
                    _logger.info("[Resend Webhook]: E-mail já processado anteriormente (ID=%s).", email_id)
                    return Response(json.dumps({'status': 'already_processed', 'id': existing.id}), content_type='application/json;charset=utf-8', status=200)

            # Se não localizou a caixa por alias ou correspondência exata, busca uma caixa associada ao primeiro destinatário válido
            if not matched_mailbox and to_list:
                first_addr = to_list[0].split('<')[-1].replace('>', '').strip().lower()
                matched_mailbox = request.env['evolars.email.mailbox'].sudo().search([
                    ('email_address', '=', first_addr)
                ], limit=1)

            # Se ainda assim não houver caixa e for do domínio, cria ou vincula à caixa padrão/institucional
            if not matched_mailbox:
                matched_mailbox = request.env['evolars.email.mailbox'].sudo().search([
                    ('is_shared', '=', True)
                ], limit=1)

            # Localiza contato do remetente
            sender_clean = from_addr.split('<')[-1].replace('>', '').strip().lower() if from_addr else ''
            partner = request.env['res.partner'].sudo().search([
                ('email', '=ilike', sender_clean)
            ], limit=1)

            # Se não houver corpo de texto/html no webhook simples, tenta buscar da API do Resend
            if not html_body and not text_body and email_id:
                details = request.env['evolars.resend.service'].sudo().fetch_received_email(email_id)
                if details:
                    html_body = details.get('html') or ''
                    text_body = details.get('text') or ''

            # Processa anexos
            attachment_ids = []
            attachments_raw = email_data.get('attachments', [])
            for att in attachments_raw:
                if isinstance(att, dict) and att.get('filename') and att.get('content'):
                    try:
                        att_rec = request.env['ir.attachment'].sudo().create({
                            'name': att.get('filename'),
                            'type': 'binary',
                            'datas': att.get('content'),
                            'res_model': 'evolars.email.message',
                        })
                        attachment_ids.append(att_rec.id)
                    except Exception as err:
                        _logger.warning("[Resend Inbound Attachment Error]: %s", str(err))

            # 3. GRAVA NO BANCO DE DADOS
            msg_vals = {
                'name': subject,
                'from_address': from_addr,
                'to_addresses': ", ".join(to_list),
                'mailbox_id': matched_mailbox.id if matched_mailbox else False,
                'partner_id': partner.id if partner else (matched_mailbox.partner_id.id if matched_mailbox else False),
                'direction': 'inbound',
                'state': 'received',
                'is_read': False,
                'body_html': html_body or (f"<p>{text_body}</p>" if text_body else '<p>(Mensagem sem conteúdo)</p>'),
                'body_text': text_body,
                'resend_email_id': str(email_id) if email_id else False,
                'raw_payload': json.dumps(data),
                'attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else False,
            }

            created_msg = request.env['evolars.email.message'].sudo().create(msg_vals)
            _logger.info("[Resend Webhook OK]: E-mail persistido com sucesso. ID=%s, ResendID=%s", created_msg.id, email_id)

            return Response(json.dumps({'status': 'success', 'id': created_msg.id}), content_type='application/json;charset=utf-8', status=200)

        except Exception as e:
            _logger.exception("[Resend Webhook Exception]: %s", str(e))
            return Response(json.dumps({'error': str(e)}), content_type='application/json;charset=utf-8', status=500)
