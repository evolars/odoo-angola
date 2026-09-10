# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class AngolaWebsiteController(http.Controller):
    @http.route(["/"], type="http", auth="public", website=True, sitemap=True)
    def index_to_slides(self, **kw):
        return request.redirect("/slides")
