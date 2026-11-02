"""Scene rendering checks preserve visual meaning and reject bad batches atomically."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'render_scenes.py'
SPEC = importlib.util.spec_from_file_location('render_scenes', SCRIPT)
renderer = importlib.util.module_from_spec(SPEC)
with mock.patch.object(sys, 'path', [str(SCRIPT.parent), *sys.path]):
    SPEC.loader.exec_module(renderer)


def scene():
    return {'w': 120, 'h': 100, 'parts': [
        {'kind': 'line', 'points': [[0, 0], [60, 0], [60, 80]], 'color': '#000000',
         'sw': 2, 'dash': True, 'label': 'A & B'},
        {'kind': 'rect', 'x': 0, 'y': 10, 'w': 20, 'h': 20, 'fill': '#FFFFFF',
         'stroke': '#000000', 'sw': 1, 'dash': True},
        {'kind': 'text', 'x': 20, 'y': 60, 'w': 80, 'h': 20,
         'text': 'Example', 'size': 12, 'color': '#000000'}]}


class RenderScenesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def cli(self, source, output, *arguments):
        argv = [str(SCRIPT), str(source), '--output', str(output), *arguments]
        with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return renderer.main()

    def test_preserves_polyline_label_dashes_and_optional_bold_text(self):
        source = renderer.render(scene())
        self.assertIn('(0,0) -- (60,0) -- (60,80)', source)
        self.assertIn(r'{A \& B}', source)
        self.assertIn('at (60.0,10.0)', source)
        self.assertEqual(source.count(',dashed'), 2)
        self.assertNotIn(r'\selectfont\bfseries', source)
        bold = scene()
        bold['parts'][-1]['bold'] = True
        self.assertIn(r'\selectfont\bfseries', renderer.render(bold))

    def test_invalid_geometry_or_color_prevents_all_batch_outputs(self):
        for field, value in [('w', float('nan')), ('fill', 'red')]:
            folder = self.folder / field
            folder.mkdir()
            (folder / 'a-good.json').write_text(json.dumps(scene()))
            invalid = scene()
            if field == 'w':
                invalid['w'] = value
            else:
                invalid['parts'][1][field] = value
            (folder / 'z-bad.json').write_text(json.dumps(invalid))
            output = self.folder / f'{field}-output'
            with self.subTest(field=field):
                self.assertEqual(self.cli(folder, output), 1)
                self.assertFalse(output.exists())

    def test_cli_accepts_a_file_or_directory_and_preserves_scene_names(self):
        folder = self.folder / 'scenes'
        folder.mkdir()
        for name in ['first', 'second']:
            (folder / f'{name}.json').write_text(json.dumps(scene()))
        single = self.folder / 'single'
        batch = self.folder / 'batch'
        self.assertEqual(self.cli(folder / 'first.json', single), 0)
        self.assertEqual(self.cli(folder, batch), 0)
        self.assertEqual({p.name for p in single.iterdir()}, {'first.tex'})
        self.assertEqual({p.name for p in batch.iterdir()}, {'first.tex', 'second.tex'})
        self.assertEqual((single / 'first.tex').read_bytes(), (batch / 'first.tex').read_bytes())

    def test_pdf_compilation_uses_each_scene_filename(self):
        source = self.folder / 'custom-scene.json'
        source.write_text(json.dumps(scene()))
        output = self.folder / 'rendered'
        with mock.patch.object(renderer, 'compile_pdf') as compile_pdf:
            self.assertEqual(self.cli(source, output, '--pdf'), 0)
        compile_pdf.assert_called_once_with(output, 'custom-scene.tex')
