# -*- coding: utf-8 -*-
{
    "name": "Evolars Angola Offline & PWA",
    "summary": "Suporte a aprendizado offline, leitor de documentos integrado e PWA para economia de dados em Angola",
    "version": "17.0.1.0.7",
    "category": "Website",
    "author": "Evolars LTDA",
    "website": "https://evolars.com.br",
    "license": "LGPL-3",
    "depends": ["website", "website_slides", "portal"],
    "data": [
        "views/layout_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "evolars_offline/static/src/css/evolars_offline.css",
            "evolars_offline/static/src/js/evolars_offline.js",
        ],
        "website_slides.slide_embed_assets": [
            "evolars_offline/static/src/css/evolars_offline.css",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
