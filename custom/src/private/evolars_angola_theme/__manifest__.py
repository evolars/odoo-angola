# -*- coding: utf-8 -*-
{
    "name": "Evolars Angola Theme",
    "summary": "Tema institucional da Evolars para o portal de E-learning em Angola",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "author": "Evolars LTDA",
    "website": "https://evolars.com.br",
    "category": "Theme/Website",
    "depends": ["website", "website_slides", "portal"],
    "data": [
        "views/layout_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "evolars_angola_theme/static/src/scss/evolars_angola_theme.scss",
        ],
    },
    "application": True,
    "installable": True,
}
