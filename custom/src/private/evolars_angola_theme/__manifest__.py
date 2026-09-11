# -*- coding: utf-8 -*-
{
    "name": "Evolars Angola Theme",
    "summary": "Tema institucional da Evolars para o portal de E-learning em Angola",
    "version": "17.0.1.0.3",
    "license": "LGPL-3",
    "author": "Evolars LTDA",
    "website": "https://evolars.com.br",
    "category": "Website",
    "depends": ["website", "website_slides", "portal"],
    "data": [
        "data/slide_channel_tag_data.xml",
        "views/layout_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "evolars_angola_theme/static/src/scss/evolars_angola_theme.scss",
            "evolars_angola_theme/static/src/css/evolars_angola_theme.css",
        ],
    },
    "application": True,
    "installable": True,
}
