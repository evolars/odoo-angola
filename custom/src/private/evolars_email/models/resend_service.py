# -*- coding: utf-8 -*-
import json
import logging
import os
import requests
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com"


class ResendService(models.AbstractModel):
    _name = 'evolars.resend.service'
    _description = 'Serviço de Comunicação com a API do Resend'

    @api.model
    def _get_api_key(self):
        """Obtém a chave da API do Resend a partir dos parâmetros de sistema ou ambiente."""
        key = self.env['ir.config_parameter'].sudo().get_param('resend.api_key')
        if not key or not key.strip():
            key = os.environ.get('RESEND_API_KEY', '')
        return (key or '').strip()

    @api.model
    def _get_system_domain(self):
        """Obtém o domínio configurado para o sistema."""
        domain = self.env['ir.config_parameter'].sudo().get_param('resend.domain')
        if not domain or not domain.strip():
            domain = os.environ.get('EMAIL_DOMAIN', 'c-edl.com')
        return (domain or '').strip().lower()

    @api.model
    def send_email(self, from_addr, to_addrs, subject, body_html, body_text=None,
                   cc_addrs=None, bcc_addrs=None, reply_to=None, attachments=None):
        """
        Dispara um e-mail via API REST do Resend.
        :param from_addr: string (ex: 'Nome <usuario@c-edl.com>')
        :param to_addrs: list of strings ou string separada por vírgulas
        :param subject: string
        :param body_html: string html
        :param body_text: string text
        :param cc_addrs: list ou string
        :param bcc_addrs: list ou string
        :param reply_to: string
        :param attachments: list of dicts [{'filename': '...', 'content': 'base64_str'}]
        :return: dict com {'id': resend_id, 'success': True}
        """
        api_key = self._get_api_key()
        if not api_key:
            raise UserError(_("Chave de API do Resend não configurada. Verifique as Configurações de E-mail."))

        # Normalização de listas de e-mails
        if isinstance(to_addrs, str):
            to_list = [addr.strip() for addr in to_addrs.replace(';', ',').split(',') if addr.strip()]
        else:
            to_list = [addr.strip() for addr in (to_addrs or []) if addr.strip()]

        if not to_list:
            raise UserError(_("Nenhum destinatário informado para o envio do e-mail."))

        payload = {
            "from": from_addr,
            "to": to_list,
            "subject": subject or '(Sem Assunto)',
            "html": body_html or f"<p>{body_text or ''}</p>",
        }
        if body_text:
            payload["text"] = body_text

        if cc_addrs:
            if isinstance(cc_addrs, str):
                cc_list = [addr.strip() for addr in cc_addrs.replace(';', ',').split(',') if addr.strip()]
            else:
                cc_list = [addr.strip() for addr in cc_addrs if addr.strip()]
            if cc_list:
                payload["cc"] = cc_list

        if bcc_addrs:
            if isinstance(bcc_addrs, str):
                bcc_list = [addr.strip() for addr in bcc_addrs.replace(';', ',').split(',') if addr.strip()]
            else:
                bcc_list = [addr.strip() for addr in bcc_addrs if addr.strip()]
            if bcc_list:
                payload["bcc"] = bcc_list

        if reply_to:
            payload["reply_to"] = reply_to

        if attachments:
            formatted_attachments = []
            for att in attachments:
                if isinstance(att, dict) and att.get('filename') and att.get('content'):
                    formatted_attachments.append({
                        "filename": att['filename'],
                        "content": att['content'],
                    })
            if formatted_attachments:
                payload["attachments"] = formatted_attachments

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{RESEND_API_URL}/emails",
                headers=headers,
                data=json.dumps(payload),
                timeout=15
            )
            data = response.json()
            if response.status_code not in (200, 201):
                err_msg = data.get('message') or data.get('error') or response.text
                _logger.error("[Resend Send Error %s]: %s", response.status_code, err_msg)
                return {
                    "success": False,
                    "error": f"Erro Resend ({response.status_code}): {err_msg}",
                    "id": False
                }

            resend_id = data.get('id')
            _logger.info("[Resend Send OK]: Email enviado com sucesso. ID=%s, To=%s", resend_id, to_list)
            return {
                "success": True,
                "id": resend_id,
                "data": data
            }
        except Exception as e:
            _logger.exception("[Resend Send Exception]: %s", str(e))
            return {
                "success": False,
                "error": f"Exceção de Conexão: {str(e)}",
                "id": False
            }

    @api.model
    def fetch_received_email(self, resend_email_id):
        """Busca os detalhes completos de um e-mail recebido na Resend Receiving API."""
        api_key = self._get_api_key()
        if not api_key or not resend_email_id:
            return False

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(
                f"{RESEND_API_URL}/emails/receiving/{resend_email_id}",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            _logger.warning("[Resend Fetch Inbound]: Não foi possível baixar detalhes extras: %s", str(e))
        return False
