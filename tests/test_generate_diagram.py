"""Behavior checks using a small synthetic catalog, without device defaults."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'generate_diagram.py'
MODULE_SPEC = importlib.util.spec_from_file_location('generate_diagram', SCRIPT)
generator = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(generator)


class GenerateDiagramTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.resources = self.folder / 'resources'
        self.resources.mkdir()
        self.scene = {'w': 100, 'h': 50, 'parts': [
            {'kind': 'rect', 'x': 0, 'y': 0, 'w': 100, 'h': 50,
             'fill': '#FFFFFF', 'stroke': '#000000', 'sw': 2},
            {'kind': 'text', 'text': 'Original', 'x': 10, 'y': 10,
             'w': 80, 'h': 20, 'size': 10, 'color': '#000000'},
            {'kind': 'line', 'points': [[0, 25], [50, 0], [100, 25]],
             'color': '#000000', 'sw': 2, 'arrow': True, 'label': 'Wire'},
        ]}
        self.catalog = {'version': 1, 'resources': {
            'fixture': {'path': 'fixture.json', 'title': 'Synthetic fixture'},
        }}
        self.catalog_path = self.resources / 'catalog.json'
        self.write_json(self.resources / 'fixture.json', self.scene)
        self.write_json(self.catalog_path, self.catalog)
        self.spec = {'steps': [{'id': 'first', 'resource': 'fixture'}]}

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def generate(self, specification):
        catalog, root = generator.load_catalog(self.catalog_path)
        return generator.generate(specification, catalog, root)

    def cli(self, specification, *arguments):
        source = self.folder / 'example.json'
        self.write_json(source, specification)
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), str(source),
             '--resources', str(self.catalog_path), *map(str, arguments)],
            capture_output=True, text=True, check=False, timeout=10)

    def assert_rejected(self, specification, message, *arguments):
        output = self.folder / 'uncreated' / 'diagram.drawio'
        result = self.cli(specification, '--output', output, *arguments)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)
        self.assertFalse(output.parent.exists(), 'Validation must precede output creation.')

    @staticmethod
    def geometry(cell):
        geometry = cell.find('mxGeometry')
        return tuple(float(geometry.get(key)) for key in ('x', 'y', 'width', 'height'))

    def test_resource_is_grouped_scaled_and_relabelled_without_mutation(self):
        specification = {'steps': [{
            'id': 'placed', 'resource': 'fixture', 'at': [20, 30],
            'size': [220, 178], 'title': 'Heading', 'caption': 'Caption',
            'text': {'Original': 'A & <B>'},
        }]}
        document = ET.fromstring(self.generate(specification))
        cells = document.findall('.//mxCell')
        group = next(cell for cell in cells if cell.get('style') == 'group;')
        children = [cell for cell in cells if cell.get('parent') == group.get('id')]
        rectangle = next(cell for cell in children if 'shape=rectangle' in cell.get('style'))
        label = next(cell for cell in children if cell.get('value') == 'A & <B>')
        wire = next(cell for cell in children if cell.get('value') == 'Wire')

        self.assertEqual(self.geometry(group), (20, 30, 220, 178))
        self.assertEqual(self.geometry(rectangle), (10, 36, 200, 100))
        self.assertEqual(self.geometry(label), (30, 56, 160, 40))
        points = wire.findall('./mxGeometry/mxPoint')
        self.assertEqual([(float(p.get('x')), float(p.get('y'))) for p in points],
                         [(10, 86), (210, 86)])
        waypoint = wire.find('./mxGeometry/Array/mxPoint')
        self.assertEqual((float(waypoint.get('x')), float(waypoint.get('y'))), (110, 36))
        self.assertEqual(wire.get('edge'), '1')
        self.assertIn('endArrow=block', wire.get('style'))
        self.assertEqual(json.loads((self.resources / 'fixture.json').read_text()), self.scene)

    def test_edges_reference_groups_and_retain_waypoints(self):
        specification = {'steps': [{'id': name, 'resource': 'fixture'} for name in ['a', 'b']],
                         'edges': [{'from': 'a', 'to': 'b', 'label': 'Next',
                                    'points': [[300, 20], [450, 40]]}]}
        cells = ET.fromstring(self.generate(specification)).findall('.//mxCell')
        edge = next(cell for cell in cells if cell.get('value') == 'Next')
        self.assertEqual((edge.get('source'), edge.get('target')), ('node-a', 'node-b'))
        points = edge.findall('./mxGeometry/Array/mxPoint')
        self.assertEqual([(p.get('x'), p.get('y')) for p in points], [('300', '20'), ('450', '40')])
        self.assertTrue({'node-a', 'node-b'}.issubset({cell.get('id') for cell in cells}))

    def test_user_ids_cannot_collide_with_internal_cells(self):
        specification = {'steps': [{'id': name, 'resource': 'fixture', 'title': 'Title',
                                    'caption': 'Caption'} for name in ['a', 'a-title', 'a-part-0']]}
        ids = [cell.get('id') for cell in ET.fromstring(self.generate(specification)).findall('.//mxCell')]
        self.assertEqual(len(ids), len(set(ids)))

    def test_repeated_generation_produces_identical_bytes(self):
        original = copy.deepcopy(self.spec)
        self.assertEqual(self.generate(self.spec), self.generate(self.spec))
        self.assertEqual(self.spec, original)

    def test_pages_inherit_layout_and_can_override_columns(self):
        steps = [{'id': name, 'resource': 'fixture'} for name in ['a', 'b']]
        specification = {'layout': {'columns': 2, 'cell_width': 200, 'cell_height': 100,
                                    'gap': 20, 'margin': 10}, 'pages': [
            {'title': 'First', 'steps': steps},
            {'title': 'Second', 'steps': steps, 'layout': {'columns': 1}},
        ]}
        pages = ET.fromstring(self.generate(specification)).findall('diagram')
        self.assertEqual([page.get('name') for page in pages], ['First', 'Second'])
        self.assertEqual(self.geometry(pages[0].find('.//mxCell[@id="node-b"]')), (230, 60, 200, 100))
        self.assertEqual(self.geometry(pages[1].find('.//mxCell[@id="node-b"]')), (10, 180, 200, 100))

    def test_custom_screen_preserves_fields_and_highlights_only_selected_value(self):
        specification = {'steps': [{'id': 'screen', 'screen': {'title': 'Custom',
            'fields': [{'label': 'Left', 'value': 'One'}, {'label': 'Right', 'value': 'Two'}],
            'selected': 1}, 'size': [532, 276]}]}
        cells = ET.fromstring(self.generate(specification)).findall('.//mxCell')
        labels = {cell.get('value'): cell for cell in cells if cell.get('value')}
        self.assertTrue({'Custom', 'Left', 'Right', 'One', 'Two'}.issubset(labels))
        self.assertIn('fontColor=#FFFFFF', labels['One'].get('style'))
        self.assertIn('fontColor=#000000', labels['Two'].get('style'))
        selected = [cell for cell in cells if 'fillColor=#FFFFFF' in cell.get('style', '')]
        self.assertEqual(len(selected), 1)
        self.assertEqual(self.geometry(selected[0]), (143, 75, 118, 75))

    def test_duplicate_step_ids_are_rejected_before_output(self):
        self.assert_rejected({'steps': self.spec['steps'] * 2}, 'Duplicate or invalid step id')

    def test_unknown_resource_is_rejected_before_output(self):
        self.assert_rejected({'steps': [{'id': 'a', 'resource': 'missing'}]}, 'Unknown resource')

    def test_invalid_geometry_is_rejected_before_output(self):
        for position in [[-1, 0], [True, 0], [float('nan'), 0], [1]]:
            with self.subTest(position=position):
                specification = copy.deepcopy(self.spec)
                specification['steps'][0]['at'] = position
                self.assert_rejected(specification, 'step.at')

    def test_unknown_keys_are_rejected_before_output(self):
        specification = copy.deepcopy(self.spec)
        specification['steps'][0]['unexpected'] = 'value'
        self.assert_rejected(specification, 'unknown fields: unexpected')

    def test_validate_rejects_invalid_resource_geometry_without_output(self):
        cases = [
            (0, {'w': -10}, 'primitive w'),
            (0, {'x': float('nan')}, 'primitive x'),
            (0, {'kind': 'ellipse', 'y': float('inf')}, 'primitive y'),
            (1, {'size': float('inf')}, 'font size'),
            (2, {'points': [[0, 0], [float('nan'), 10]]}, 'line point'),
            (2, {'sw': float('inf')}, 'line stroke width'),
        ]
        for index, changes, message in cases:
            with self.subTest(primitive=index, changes=changes):
                scene = copy.deepcopy(self.scene)
                scene['parts'][index].update(changes)
                self.write_json(self.resources / 'fixture.json', scene)

                self.assert_rejected(self.spec, message, '--validate')

    def test_invalid_screen_selection_is_rejected_before_output(self):
        self.assert_rejected({'steps': [{'id': 'a', 'screen': {
            'fields': [{'label': 'Only', 'value': 'Value'}], 'selected': 1}}]}, 'screen.selected')

    def test_escaping_resource_path_is_rejected_before_output(self):
        self.write_json(self.folder / 'outside.json', self.scene)
        self.catalog['resources']['fixture']['path'] = '../outside.json'
        self.write_json(self.catalog_path, self.catalog)
        self.assert_rejected(self.spec, 'Resource path escapes catalog directory')

    def test_unused_text_replacement_is_rejected_before_output(self):
        specification = copy.deepcopy(self.spec)
        specification['steps'][0]['text'] = {'Absent': 'Replacement'}
        self.assert_rejected(specification, 'Text not found in resource: Absent')

    def test_edge_to_missing_step_is_rejected_before_output(self):
        specification = copy.deepcopy(self.spec)
        specification['edges'] = [{'from': 'first', 'to': 'missing'}]
        self.assert_rejected(specification, 'existing step ids')

    def test_cli_validate_writes_no_output(self):
        result = self.cli(self.spec, '--validate')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Specification is valid.', result.stdout)
        self.assertFalse((self.folder / 'example.drawio').exists())

    def test_cli_default_output_uses_specification_filename(self):
        result = self.cli(self.spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.folder / 'example.drawio'
        self.assertEqual(output.read_bytes(), self.generate(self.spec))
        self.assertIn(str(output), result.stdout)


if __name__ == '__main__':
    unittest.main()
