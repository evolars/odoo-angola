# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import controllers


def post_init_hook(env):
    """Gera e sincroniza automaticamente as caixas postais institucionais."""
    env['evolars.email.mailbox'].sudo().action_provision_all_mailboxes()
