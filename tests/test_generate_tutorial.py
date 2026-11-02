"""Tutorial behavior checks use synthetic content and tiny local image fixtures."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'generate_tutorial.py'
SPEC = importlib.util.spec_from_file_location('generate_tutorial', SCRIPT)
tutorial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tutorial)


def pixel(rgb):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0' + bytes(rgb))) + chunk(b'IEND', b''))


class GenerateTutorialTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.input = self.folder / 'content'
        self.input.mkdir()
        assets = self.folder / 'assets'
        assets.mkdir()
        for name, color in [('control', (0, 0, 0)), ('screen', (255, 255, 255))]:
            (assets / f'{name}.png').write_bytes(pixel(color))

    @staticmethod
    def content():
        return {'title': 'Synthetic tutorial', 'pages': [{'title': 'Page one', 'steps': [{'title': 'Alpha'}]}]}

    def cli(self, content):
        source = self.input / 'example.json'
        source.write_text(json.dumps(content), encoding='utf-8')
        output = self.folder / 'output'
        with mock.patch.object(sys, 'argv', [str(SCRIPT), str(source), '--output', str(output)]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return tutorial.main(), output

    def test_escapes_text_and_preserves_permitted_whitespace(self):
        self.assertEqual(tutorial.tex('50% & A_B #1 $5 {x}'), r'50\% \& A\_B \#1 \$5 \{x\}')
        self.assertEqual(tutorial.tex('a\\b ~ ^'), r'a\textbackslash{}b \textasciitilde{} \textasciicircum{}')
        self.assertEqual(tutorial.tex('line\n\tindent'), 'line\n\tindent')
        with self.assertRaises(ValueError):
            tutorial.tex('bad\x00text')

    def test_pages_keep_step_order_and_continuous_numbering(self):
        content = self.content()
        content['pages'][0]['steps'].append({'title': 'Beta'})
        content['pages'].append({'title': 'Page two', 'steps': [{'title': 'Gamma'}]})
        source, assets = tutorial.render(content)
        positions = [source.index(token) for token in [r'\begin{stepbox}{01}{Alpha}',
                     r'\begin{stepbox}{02}{Beta}', r'\newpage', r'\begin{stepbox}{03}{Gamma}']]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(assets, {})

    def test_content_that_looks_like_template_tokens_stays_literal(self):
        content = self.content()
        content['title'] = 'Keep @@CONTENT@@'
        content['pages'][0]['steps'][0]['paragraphs'] = ['Keep @@TITLE@@ and @@CONTENT@@']
        source, _ = tutorial.render(content)
        self.assertIn('Keep @@CONTENT@@', source)
        self.assertIn('Keep @@TITLE@@ and @@CONTENT@@', source)

    def test_walkthrough_copies_distinct_control_and_screen_assets_relative_to_content(self):
        content = self.content()
        content['pages'][0]['steps'][0]['walkthrough'] = [{'action': 'Example action',
            'figure': {'path': '../assets/control.png'}, 'screen': {'path': '../assets/screen.png'}}]
        source, assets = tutorial.render(content, self.input)
        self.assertEqual({path.name for path in assets.values()}, {'control.png', 'screen.png'})
        self.assertEqual(len(assets), 2)
        self.assertLess(source.index(next(name for name in assets if '-nav-' in name)),
                        source.index(next(name for name in assets if '-screen-' in name)))
        status, output = self.cli(content)
        self.assertEqual(status, 0)
        self.assertEqual((output / 'main.tex').read_text(), source)
        for name, original in assets.items():
            self.assertEqual((output / name).read_bytes(), original.read_bytes())

    def test_rejects_invalid_tables_and_connection_shapes(self):
        for table in [{'headers': [], 'rows': []}, {'headers': ['A', 'B'], 'rows': [['one']]}]:
            with self.subTest(table=table), self.assertRaises(ValueError):
                tutorial.table(table)
        for pairs in ['not a list', [['only one']], [['A', 'B', 'C']]]:
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                tutorial.connections(pairs)

    def test_figure_height_and_trim_require_finite_nonboolean_numbers(self):
        variants = [{'height_mm': value} for value in [True, 4, 101, float('nan'), float('inf')]]
        variants += [{'trim': value} for value in [[0, 0, 0], [0, -1, 0, 0], [0, True, 0, 0], [0, float('nan'), 0, 0]]]
        for values in variants:
            with self.subTest(values=values), self.assertRaises(ValueError):
                tutorial.figure_tex({'path': '../assets/control.png', **values}, 'fixture', self.input, {})
        rendered = tutorial.figure_tex({'path': '../assets/control.png', 'height_mm': 5, 'trim': [0, 1, 2, 3]},
                                       'fixture', self.input, {})
        self.assertIn('height=5mm', rendered)
        self.assertIn('trim=0pt 1pt 2pt 3pt,clip', rendered)

    def test_links_validate_urls_and_escape_targets_and_labels(self):
        rendered = tutorial.link({'url': 'https://example.test/a_b~c?q={x}&n=1&price=$5', 'label': 'Watch & learn'})
        self.assertIn(r'\%24', rendered)
        self.assertIn(r'\string~', rendered)
        self.assertIn(r'\%7Bx\%7D\&n=1', rendered)
        self.assertIn(r'Watch \& learn', rendered)
        for url in ['file:///tmp/a', 'javascript:alert(1)', 'https://example.test/a b', 'https://example.test/a\\b']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                tutorial.link({'url': url, 'label': 'Invalid'})

    def test_validation_error_leaves_existing_output_and_assets_untouched(self):
        output = self.folder / 'output'
        output.mkdir()
        (output / 'main.tex').write_text('Keep this source.')
        content = self.content()
        content['pages'][0]['steps'][0].update(figure={'path': '../assets/control.png'},
            links=[{'label': 'Invalid', 'url': 'file:///tmp/a'}])
        status, _ = self.cli(content)
        self.assertEqual(status, 1)
        self.assertEqual((output / 'main.tex').read_text(), 'Keep this source.')
        self.assertFalse((output / 'images').exists())

    def test_compiler_invocation_uses_two_passes_with_shell_escape_disabled(self):
        with mock.patch.object(tutorial.shutil, 'which', return_value='/fake/pdflatex'), \
                mock.patch.object(tutorial.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            tutorial.compile_pdf(self.folder, 'chapter.tex')
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertIn('-no-shell-escape', call.args[0])
            self.assertEqual(call.args[0][-1], 'chapter.tex')
            self.assertEqual(call.kwargs['cwd'], self.folder)
            self.assertFalse(call.kwargs.get('shell', False))
