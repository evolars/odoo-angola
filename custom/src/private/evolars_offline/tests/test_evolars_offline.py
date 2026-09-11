# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree as ET
from unittest import TestCase


class TestEvolarsOfflineTemplates(TestCase):

    def setUp(self):
        super().setUp()
        self.xml_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'views', 'layout_templates.xml'
        )

    def test_01_xml_validity(self):
        tree = ET.parse(self.xml_path)
        self.assertIsNotNone(tree.getroot())

    def test_02_collapsed_course_card_structure(self):
        with open(self.xml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('evolars-offline-course-card', content)
        self.assertNotIn('card h-100 shadow-sm border evolars-offline-course-card', content)
        self.assertNotIn('d-flex flex-column justify-content-between p-4', content)
        self.assertIn('evolars-course-title-toggle', content)
        self.assertIn('evolars-toggle-chevron', content)
        self.assertIn('evolarsToggleCourseSlides', content)
        self.assertIn('offline-slides-list-', content)
        self.assertIn('d-none mt-3 pt-3 border-top evolars-slides-collapse', content)

    def test_03_js_toggle_and_chevron_logic(self):
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'src', 'js', 'evolars_offline.js'
        )
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        self.assertIn('window.evolarsToggleCourseSlides = function (channelId)', js_content)
        self.assertIn('fa-chevron-up', js_content)
        self.assertIn('fa-chevron-down', js_content)
        self.assertIn('aria-expanded', js_content)
