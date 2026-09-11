# -*- coding: utf-8 -*-
import io
import re
import os
import json
import base64
import zipfile
from odoo import http
from odoo.http import request


def slugify_filename(name):
    clean = re.sub(r'[\\/*?:"<>|]', '', name)
    clean = clean.strip().replace(' ', '_')
    return clean[:60] or 'material'


class EvolarsOfflineController(http.Controller):

    @http.route(['/sw.js'], type='http', auth='public', website=False, sitemap=False)
    def service_worker(self):
        sw_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'src', 'js', 'sw.js'
        )
        if not os.path.exists(sw_path):
            return request.not_found()

        with open(sw_path, 'rb') as f:
            content = f.read()

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/javascript; charset=utf-8'),
                ('Service-Worker-Allowed', '/'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ]
        )

    @http.route(['/site.webmanifest'], type='http', auth='public', website=False, sitemap=False)
    def webmanifest(self):
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'src', 'site.webmanifest'
        )
        if not os.path.exists(manifest_path):
            return request.not_found()

        with open(manifest_path, 'rb') as f:
            content = f.read()

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/manifest+json; charset=utf-8'),
                ('Cache-Control', 'public, max-age=86400'),
            ]
        )

    @http.route('/slides/channel/<int:channel_id>/download_package', type='http', auth='public', website=True)
    def download_channel_package(self, channel_id, **kw):
        channel = request.env['slide.channel'].sudo().browse(channel_id)
        if not channel.exists() or not channel.is_published:
            return request.not_found()

        slides = channel.slide_ids.filtered(
            lambda s: s.slide_category == 'document' and s.is_published and s.binary_content
        ).sorted(lambda s: s.sequence)

        if not slides:
            return request.make_response(
                "Nenhum material em PDF disponível para download neste curso.",
                headers=[('Content-Type', 'text/plain; charset=utf-8')]
            )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            readme_text = f"""=====================================================
CURSO: {channel.name}
PLATAFORMA: Evolars Angola (https://angola.evolars.com.br)
=====================================================

Este pacote contém todas as apostilas e materiais em PDF do curso,
otimizado para estudo offline sem consumo contínuo de dados móveis.

Materiais inclusos ({len(slides)} lições):
"""
            for idx, slide in enumerate(slides, start=1):
                safe_title = slugify_filename(slide.name)
                fname = f"{idx:02d}_{safe_title}.pdf"
                readme_text += f"\n  {idx:02d}. {slide.name} ({fname})"
                pdf_data = base64.b64decode(slide.binary_content)
                zf.writestr(f"{slugify_filename(channel.name)}/{fname}", pdf_data)

            readme_text += "\n\nBons estudos! Evolars Angola — Capacitação Tecnológica Aberta.\n"
            zf.writestr(f"{slugify_filename(channel.name)}/LEIA-ME.txt", readme_text)

        zip_bytes = buf.getvalue()
        zip_filename = f"Evolars_{slugify_filename(channel.name)}.zip"

        return request.make_response(
            zip_bytes,
            headers=[
                ('Content-Type', 'application/zip'),
                ('Content-Disposition', f'attachment; filename="{zip_filename}"'),
                ('Content-Length', str(len(zip_bytes))),
                ('Cache-Control', 'public, max-age=3600'),
            ]
        )

    @http.route('/slides/channel/<int:channel_id>/offline_manifest', type='json', auth='public')
    def channel_offline_manifest(self, channel_id, **kw):
        channel = request.env['slide.channel'].sudo().browse(channel_id)
        if not channel.exists() or not channel.is_published:
            return {'error': 'Curso não encontrado'}

        slides = channel.slide_ids.filtered(
            lambda s: s.slide_category == 'document' and s.is_published and s.binary_content
        ).sorted(lambda s: s.sequence)

        return {
            'id': channel.id,
            'name': channel.name,
            'description': channel.description or '',
            'total_slides': len(slides),
            'cover_url': f'/web/image/slide.channel/{channel.id}/image_512' if channel.image_1920 else False,
            'package_url': f'/slides/channel/{channel.id}/download_package',
            'slides': [
                {
                    'id': s.id,
                    'name': s.name,
                    'sequence': s.sequence,
                    'is_preview': s.is_preview,
                    'pdf_url': f'/web/content/slide.slide/{s.id}/binary_content/{slugify_filename(s.name)}.pdf',
                } for s in slides
            ]
        }

    @http.route('/slides/sync_progress', type='json', auth='public', methods=['POST'])
    def sync_progress(self, slide_ids=None, **kw):
        slide_ids = slide_ids or []
        if not slide_ids:
            return {'status': 'empty', 'synced': 0}

        user = request.env.user
        if user._is_public():
            return {
                'status': 'anonymous',
                'message': 'Progresso salvo localmente no aparelho. Inicie sessão para sincronizar com a sua conta.',
                'synced': len(slide_ids),
            }

        slides = request.env['slide.slide'].sudo().browse(slide_ids).filtered(lambda s: s.exists())
        if slides:
            slides.with_user(user)._action_mark_completed()

        return {
            'status': 'ok',
            'synced': len(slides),
            'user': user.name,
        }

    @http.route(['/slides/offline'], type='http', auth='public', website=True)
    def offline_library(self, **kw):
        return request.render('evolars_offline.offline_library_template', {})
