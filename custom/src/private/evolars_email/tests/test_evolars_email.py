# -*- coding: utf-8 -*-
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestEvolarsEmailHub(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config_param = self.env['ir.config_parameter'].sudo()
        self.config_param.set_param('resend.domain', 'c-edl.com')
        self.config_param.set_param('resend.api_key', 're_test_key_123456789')
        self.config_param.set_param('resend.auto_create_partner_email', 'True')
        self.config_param.set_param('resend.default_from', 'Secretaria C-EDL <secretaria@c-edl.com>')

        # Cria uma caixa compartilhada para a secretaria
        self.mb_secretaria = self.env['evolars.email.mailbox'].create({
            'name': 'Secretaria Escolar',
            'email_address': 'secretaria@c-edl.com',
            'is_shared': True,
        })

    def test_01_auto_provisioning_partner_email(self):
        """Testa geração automática de e-mail institucional e criação da Mailbox ao criar contato."""
        partner = self.env['res.partner'].create({
            'name': 'Carlos Eduardo da Silva',
        })
        self.assertEqual(partner.email, 'carlos.silva@c-edl.com')

        # Verifica se a mailbox foi provisionada
        mb = self.env['evolars.email.mailbox'].search([('partner_id', '=', partner.id)], limit=1)
        self.assertTrue(mb, "Deveria ter criado uma Mailbox para o contato.")
        self.assertEqual(mb.email_address, 'carlos.silva@c-edl.com')
        self.assertFalse(mb.is_shared)

    def test_02_slugify_and_homonyms_resolution(self):
        """Testa resolução de homônimos adicionando sufixo numérico."""
        p1 = self.env['res.partner'].create({'name': 'Mariana Souza'})
        p2 = self.env['res.partner'].create({'name': 'Mariana Souza'})
        p3 = self.env['res.partner'].create({'name': 'Mariana Souza'})

        self.assertEqual(p1.email, 'mariana.souza@c-edl.com')
        self.assertEqual(p2.email, 'mariana.souza2@c-edl.com')
        self.assertEqual(p3.email, 'mariana.souza3@c-edl.com')

    def test_03_mailbox_and_alias_creation(self):
        """Testa criação de aliases e contagem de mensagens."""
        alias = self.env['evolars.email.alias'].create({
            'name': 'Atendimento Geral',
            'alias_address': 'atendimento@c-edl.com',
            'mailbox_id': self.mb_secretaria.id,
        })
        self.assertEqual(alias.mailbox_id, self.mb_secretaria)

        # Não deve permitir criar alias com e-mail duplicado
        with self.assertRaises(Exception):
            self.env['evolars.email.alias'].create({
                'name': 'Atendimento Duplicado',
                'alias_address': 'atendimento@c-edl.com',
                'mailbox_id': self.mb_secretaria.id,
            })

    def test_04_resend_outbound_composer_mock(self):
        """Testa assistente de composição de e-mail e chamada à API Resend mockada."""
        destinatario = self.env['res.partner'].create({
            'name': 'Professor Roberto Alencar',
        })

        composer = self.env['evolars.email.composer'].create({
            'from_mailbox_id': self.mb_secretaria.id,
            'to_partner_ids': [(4, destinatario.id)],
            'subject': 'Convocação para Reunião Pedagógica',
            'body_html': '<p>Prezado professor, contamos com sua presença.</p>',
        })

        fake_resend_response = {
            'success': True,
            'id': 'resend_msg_test_98765',
            'data': {'id': 'resend_msg_test_98765'}
        }

        with patch.object(self.env['evolars.resend.service'], 'send_email', return_value=fake_resend_response) as mock_send:
            composer.action_send_email()
            mock_send.assert_called_once()

        # Verifica mensagem gravada no banco
        msg = self.env['evolars.email.message'].search([('resend_email_id', '=', 'resend_msg_test_98765')], limit=1)
        self.assertTrue(msg)
        self.assertEqual(msg.direction, 'outbound')
        self.assertEqual(msg.state, 'sent')
        self.assertEqual(msg.from_address, 'secretaria@c-edl.com')
        self.assertEqual(msg.to_addresses, destinatario.email)
        self.assertTrue(msg.is_read)

    def test_05_message_state_actions(self):
        """Testa transições de estado, marcação de leitura, lixeira e favoritos."""
        msg = self.env['evolars.email.message'].create({
            'name': 'Aviso de Matrícula',
            'from_address': 'externo@gmail.com',
            'to_addresses': 'secretaria@c-edl.com',
            'mailbox_id': self.mb_secretaria.id,
            'direction': 'inbound',
            'state': 'received',
            'is_read': False,
            'is_starred': False,
        })

        # Marcar como lida
        msg.action_mark_read()
        self.assertTrue(msg.is_read)

        # Alternar estrela
        msg.action_toggle_star()
        self.assertTrue(msg.is_starred)
        msg.action_toggle_star()
        self.assertFalse(msg.is_starred)

        # Mover para lixeira e restaurar
        msg.action_move_trash()
        self.assertEqual(msg.state, 'trash')
        msg.action_restore()
        self.assertEqual(msg.state, 'received')
