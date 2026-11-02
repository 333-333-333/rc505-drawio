"""Synthetic fixtures verify XML validation and formatting without network access."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'lint_xml.py'
SPEC = importlib.util.spec_from_file_location('lint_xml', SCRIPT)
linter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(linter)
MODEL = ('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
         '<mxCell id="2" parent="1" vertex="1"><mxGeometry x="10" y="20" width="100" height="60"/>'
         '</mxCell></root></mxGraphModel>')


def library(model=MODEL):
    root = ET.Element('mxlibrary')
    root.text = json.dumps([{'title': 'Synthetic fixture', 'w': 100, 'h': 60, 'xml': model}])
    return ET.tostring(root, encoding='unicode')


class LintXmlTests(unittest.TestCase):
    def test_formats_external_and_embedded_models(self):
        document = '<mxfile><diagram id="one">' + MODEL + '</diagram></mxfile>'
        self.assertIn('\n  <diagram', linter.canonicalize(document))
        formatted = linter.canonicalize(library())
        entry = json.loads(ET.fromstring(formatted).text)[0]
        self.assertIn('\n  <root>', entry['xml'])
        self.assertEqual(ET.fromstring(entry['xml']).find('.//mxCell[@id="2"]').get('parent'), '1')
        self.assertEqual(linter.canonicalize(formatted), formatted)

    def test_rejects_malformed_xml_and_library_json(self):
        for text, message in [('<mxfile>', 'Malformed XML'), ('<mxlibrary>bad</mxlibrary>', 'Malformed library JSON')]:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, message):
                linter.canonicalize(text)

    def test_rejects_invalid_references(self):
        for attribute in ('parent', 'source', 'target'):
            model = MODEL.replace('id="2" parent="1"', f'id="2" {attribute}="missing"')
            with self.subTest(attribute=attribute), self.assertRaisesRegex(ValueError, f'Unknown {attribute}'):
                linter.canonicalize(model)

    def test_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, 'unique'):
            linter.canonicalize(MODEL.replace('id="2"', 'id="1"'))

    def test_references_cannot_target_geometry_ids(self):
        for attribute in ('parent', 'source', 'target'):
            model = ET.fromstring(MODEL)
            model.find('.//mxGeometry').set('id', 'geometry-only')
            edge = ET.SubElement(model.find('root'), 'mxCell', id='edge', parent='1', source='2', target='2')
            edge.set(attribute, 'geometry-only')
            with self.subTest(attribute=attribute), self.assertRaisesRegex(ValueError, f'Unknown {attribute}'):
                linter.canonicalize(ET.tostring(model, encoding='unicode'))

    def test_references_accept_ids_on_immediate_object_wrappers(self):
        for tag in ('object', 'UserObject'):
            model = ET.fromstring(MODEL)
            root = model.find('root')
            cell = root.find('mxCell[@id="2"]')
            root.remove(cell)
            del cell.attrib['id']
            ET.SubElement(root, tag, id='wrapped').append(cell)
            ET.SubElement(root, 'mxCell', id='edge', parent='1', source='wrapped', target='1')
            with self.subTest(wrapper=tag):
                formatted = ET.fromstring(linter.canonicalize(ET.tostring(model, encoding='unicode')))
                self.assertEqual(formatted.find('.//mxCell[@id="edge"]').get('source'), 'wrapped')

    def test_page_ids_are_unique_but_models_have_separate_id_scopes(self):
        document = '<mxfile><diagram id="one">' + MODEL + '</diagram><diagram id="two">' + MODEL + '</diagram></mxfile>'
        self.assertEqual(len(ET.fromstring(linter.canonicalize(document)).findall('diagram')), 2)
        with self.assertRaisesRegex(ValueError, 'Diagram IDs'):
            linter.canonicalize(document.replace('id="two"', 'id="one"'))

    def test_rejects_nonfinite_coordinates_and_negative_sizes(self):
        for before, after in [('x="10"', 'x="NaN"'), ('height="60"', 'height="Infinity"'), ('width="100"', 'width="-1"')]:
            with self.subTest(after=after), self.assertRaisesRegex(ValueError, 'finite'):
                linter.canonicalize(library(MODEL.replace(before, after)))

    def test_rejects_compressed_content_explicitly(self):
        for text in [library('encoded-content'), '<mxfile><diagram>encoded-content</diagram></mxfile>']:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'compressed'):
                linter.canonicalize(text)

    def test_fix_is_idempotent_and_check_reports_formatting(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            path = Path(folder) / 'fixture.xml'
            path.write_text(library(), encoding='utf-8')
            self.assertEqual(linter.main([str(path)]), 1)
            self.assertEqual(linter.main(['--fix', str(path)]), 0)
            first = path.read_bytes()
            self.assertEqual(linter.main(['--fix', str(path)]), 0)
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(linter.main(['--check', str(path)]), 0)

    def test_fix_does_not_rewrite_invalid_file(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            path = Path(folder) / 'invalid.drawio'
            path.write_text(MODEL.replace('width="100"', 'width="-1"'), encoding='utf-8')
            original = path.read_bytes()
            self.assertEqual(linter.main(['--fix', str(path)]), 1)
            self.assertEqual(path.read_bytes(), original)
