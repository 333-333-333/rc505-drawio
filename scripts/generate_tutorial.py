#!/usr/bin/env python3
"""Convert JSON content into a LaTeX tutorial; optionally compile its PDF."""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, urlsplit

BASE = Path(__file__).resolve().parents[1]
TEMPLATE = BASE / 'templates' / 'tutorial.tex'
ACTIONS = {'press': 1, 'twist': 2, 'slide': 3, 'connect': 0, 'info': 0}
ESCAPES = dict(zip('\\&%$#_{}~^',
    [r'\textbackslash{}', r'\&', r'\%', r'\$', r'\#', r'\_',
     r'\{', r'\}', r'\textasciitilde{}', r'\textasciicircum{}']))


def tex(value):
    if not isinstance(value, str):
        raise ValueError('Text must be a JSON string.')
    if any(ord(char) < 32 and char not in '\n\t' for char in value):
        raise ValueError('Text contains unsupported control characters.')
    return ''.join(ESCAPES.get(char, char) for char in value)


def link(item):
    url = item['url']
    if not isinstance(url, str) or any(char.isspace() or ord(char) < 32 or char == '\\' for char in url):
        raise ValueError('Links must be complete HTTP or HTTPS URLs without whitespace or backslashes.')
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.netloc:
        raise ValueError('Links must be complete HTTP or HTTPS URLs.')
    encoded = quote(url, safe=":/?#[]@!&'()*+,;=%~-._")
    escapes = {'&': r'\&', '%': r'\%', '#': r'\#', '_': r'\_', '~': r'\string~'}
    target = ''.join(escapes.get(char, char) for char in encoded)
    return r'\resourceLink{' + target + '}{' + tex(item['label']) + '}'


def table(data):
    headers, rows = data['headers'], data['rows']
    if (not isinstance(headers, list) or not 1 <= len(headers) <= 4
            or not isinstance(rows, list)
            or any(not isinstance(row, list) or len(row) != len(headers) for row in rows)):
        raise ValueError('Tables support 1-4 columns; every row must match the headers.')
    columns = '|'.join([r'>{\raggedright\arraybackslash}X'] * len(headers))
    lines = [r'\begingroup\small\renewcommand{\arraystretch}{1.22}',
             r'\begin{tabularx}{\linewidth}{' + columns + '}', r'\rowcolor{paper}']
    lines.append(' & '.join(r'\textbf{' + tex(h) + '}' for h in headers) + r' \\')
    lines.extend(' & '.join(tex(v) for v in row) + r' \\' for row in rows)
    return '\n'.join(lines + [r'\end{tabularx}\endgroup'])


def connections(pairs):
    if not isinstance(pairs, list) or any(not isinstance(pair, list) or len(pair) != 2 for pair in pairs):
        raise ValueError('Each connection needs exactly one source and one destination.')
    lines = [r'\begin{center}\begin{tikzpicture}[x=1mm,y=1mm,',
             r'port/.style={draw=rulecolor,fill=paper,rounded corners=1mm,',
             r'minimum width=34mm,minimum height=6.5mm,font=\small\bfseries}]']
    for index, (source, target) in enumerate(pairs):
        y, color = -index * 8, ('cableblack' if index % 2 == 0 else 'cablegray')
        lines += [rf'\node[port] (s{index}) at (0,{y}) {{{tex(source)}}};',
                  rf'\node[port] (t{index}) at (100,{y}) {{{tex(target)}}};',
                  rf'\draw[draw={color},line width=1.4pt,-{{Stealth[length=2mm]}}] (s{index})--(t{index});']
    return '\n'.join(lines + [r'\end{tikzpicture}\end{center}'])


def figure_tex(figure, name, input_dir, figures):
    source = (input_dir / figure['path']).resolve()
    if source.suffix.lower() not in ('.pdf', '.png', '.jpg', '.jpeg') or not source.is_file():
        raise ValueError(f'Missing figure or unsupported format: {source}')
    height = figure.get('height_mm', 45)
    if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or not 5 <= height <= 100:
        raise ValueError('Figure height must be between 5 and 100 mm.')
    name = 'images/' + name + source.suffix.lower()
    figures[name] = source
    options = r'width=\linewidth,height=' + str(height) + r'mm,keepaspectratio'
    if figure.get('trim'):
        trim = figure['trim']
        if (not isinstance(trim, list) or len(trim) != 4
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in trim)):
            raise ValueError('Figure trim needs four nonnegative point values: left, bottom, right, top.')
        options += ',trim=' + ' '.join(str(v) + 'pt' for v in trim) + ',clip'
    lines = [r'\par\smallskip{\centering\includegraphics[' + options
             + ']{' + name + r'}\par}\smallskip']
    if figure.get('caption'):
        lines.append(r'{\footnotesize\color{muted}' + tex(figure['caption']) + r'\par}')
    return '\n'.join(lines)


def walkthrough(items, number, input_dir, figures):
    if not isinstance(items, list) or not 1 <= len(items) <= 8:
        raise ValueError('A walkthrough needs 1-8 action panels.')
    lines = []
    for index,item in enumerate(items, 1):
        if index % 2:
            lines.append(r'\noindent')
        lines += [r'\begin{minipage}[t]{.485\linewidth}\vspace{0pt}',
                  r'\begin{tcolorbox}[colback=white,colframe=rulecolor,boxrule=.5pt,arc=1mm,',
                  r'left=2mm,right=2mm,top=2mm,bottom=2mm,before skip=2pt,after skip=2pt]',
                  r'{\small\bfseries ' + str(index) + '. ' + tex(item['action']) + r'}\par']
        if item.get('figure'):
            lines.append(figure_tex(item['figure'], f'step-{number:02d}-nav-{index:02d}', input_dir, figures))
        if item.get('screen'):
            lines.append(figure_tex(item['screen'], f'step-{number:02d}-screen-{index:02d}', input_dir, figures))
        if item.get('result'):
            lines.append(r'{\small\raggedright ' + tex(item['result']) + r'\par}')
        lines.append(r'\end{tcolorbox}\end{minipage}')
        lines.append(r'\hfill' if index % 2 and index < len(items) else r'\par')
    return '\n'.join(lines)


def render_step(step, number, input_dir, figures):
    action = step.get('action', 'info')
    if action not in ACTIONS:
        raise ValueError(f'Unknown action: {action}. Options: {", ".join(ACTIONS)}')
    lines = [rf'\begin{{stepbox}}{{{number:02d}}}{{{tex(step["title"])}}}{{{ACTIONS[action]}}}']
    if step.get('route'):
        path = r' $\rightarrow$ '.join(tex(part) for part in step['route'])
        lines.append(r'\route{' + path + '}')
    if step.get('access'):
        lines.append(figure_tex(step['access'], f'step-{number:02d}-access', input_dir, figures))
    lines.extend(tex(p) + r'\par' for p in step.get('paragraphs', []))
    if step.get('walkthrough'):
        lines.append(walkthrough(step['walkthrough'], number, input_dir, figures))
    if step.get('figure'):
        lines.append(figure_tex(step['figure'], f'step-{number:02d}', input_dir, figures))
    if step.get('connections'):
        lines.append(connections(step['connections']))
    if step.get('items'):
        lines += [r'\begin{itemize}']
        lines += [r'\item ' + tex(item) for item in step['items']]
        lines += [r'\end{itemize}']
    if step.get('table'):
        lines.append(table(step['table']))
    if step.get('knobs'):
        if len(step['knobs']) > 4:
            raise ValueError('The visual row supports up to four knobs.')
        lines.append(r'\vspace{3pt}')
        lines.append('%\n'.join(rf'\knob{{{i}}}{{{tex(label)}}}' for i,label in enumerate(step['knobs'],1)))
        lines.append(r'\par')
    if step.get('links'):
        lines.extend(link(item) for item in step['links'])
    if step.get('note'):
        lines.append(r'\notebox{' + tex(step['note']) + '}')
    return '\n'.join(lines + [r'\end{stepbox}'])


def render(data, input_dir=Path('.')):
    if not isinstance(data, dict):
        raise ValueError('Tutorial content must be a JSON object.')
    pages = data['pages']
    if not isinstance(pages, list) or not pages:
        raise ValueError('At least one page is required.')
    body, number, figures = [], 0, {}
    for index, page in enumerate(pages, 1):
        if not isinstance(page, dict) or not isinstance(page.get('steps'), list) or not page['steps']:
            raise ValueError('Each page must be an object with a nonempty steps array.')
        if index > 1:
            body.append(r'\newpage')
        body.append(rf'\pagehead{{{index:02d} / {len(pages):02d}}}{{{tex(page["title"])}}}{{{tex(page.get("intro", ""))}}}')
        if page.get('figure'):
            body.append(figure_tex(page['figure'], f'page-{index:02d}', input_dir, figures))
        for step in page['steps']:
            if not isinstance(step, dict):
                raise ValueError('Each step must be an object.')
            number += 1
            body.append(render_step(step, number, input_dir, figures))
        for note in page.get('notes', []):
            body.append(r'\notebox{' + tex(note) + '}')
        if page.get('links'):
            body.extend(link(item) for item in page['links'])
    replacements = {'@@TITLE@@': tex(data['title']), '@@AUTHOR@@': tex(data.get('author', 'Tutorial')),
                    '@@EYEBROW@@': tex(data.get('eyebrow', data['title'])),
                    '@@FOOTER@@': tex(data.get('footer', data['title'])), '@@CONTENT@@': '\n'.join(body)}
    template = TEMPLATE.read_text(encoding='utf-8')
    template = re.sub(r'@@[A-Z]+@@', lambda match: replacements.get(match.group(), match.group()), template)
    return template, figures


def compile_pdf(output, filename='main.tex'):
    executable = shutil.which('pdflatex')
    mac_tex = Path('/Library/TeX/texbin/pdflatex')
    if not executable and mac_tex.exists():
        executable = str(mac_tex)
    if not executable:
        raise ValueError('LaTeX generated. Install TeX Live/MacTeX or compile the source in a LaTeX editor.')
    args = [executable, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error', filename]
    for _ in range(2):
        result = subprocess.run(args, cwd=output, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f'LaTeX failed. Check {output / Path(filename).with_suffix(".log")}\n' + result.stdout[-2000:])
    print(f'PDF: {output / Path(filename).with_suffix(".pdf")}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('content', type=Path, help='UTF-8 JSON content file')
    parser.add_argument('--output', type=Path, required=True, help='Output folder for main.tex and its PDF')
    parser.add_argument('--pdf', action='store_true', help='Compile with the available system pdflatex')
    options = parser.parse_args()
    try:
        data = json.loads(options.content.read_text(encoding='utf-8'))
        source, figures = render(data, options.content.resolve().parent)
        output = options.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        for name, figure in figures.items():
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.resolve() != figure:
                shutil.copy2(figure, destination)
        (output / 'main.tex').write_text(source, encoding='utf-8')
        print(f'LaTeX: {output / "main.tex"}')
        if options.pdf:
            compile_pdf(output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
