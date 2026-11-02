#!/usr/bin/env python3
"""Render scene JSON files as editable LaTeX and optional vector PDF figures."""
import argparse
import math
from pathlib import Path
import re
import sys

from generate_diagram import number, read_json, validate_part
from generate_tutorial import compile_pdf, tex

SYMBOLS = {'▶': r'\ensuremath{\blacktriangleright}', '◀': r'\ensuremath{\blacktriangleleft}',
           '●': r'\ensuremath{\bullet}', '■': r'\ensuremath{\blacksquare}',
           '○': r'\ensuremath{\circ}', '→': r'\ensuremath{\rightarrow}',
           '←': r'\ensuremath{\leftarrow}', '↑': r'\ensuremath{\uparrow}',
           '↓': r'\ensuremath{\downarrow}', '↔': r'\ensuremath{\leftrightarrow}',
           '↕': r'\ensuremath{\updownarrow}', '↻': r'\ensuremath{\circlearrowright}',
           '↺': r'\ensuremath{\circlearrowleft}', '∞': r'\ensuremath{\infty}',
           '≥': r'\ensuremath{\geq}', '≤': r'\ensuremath{\leq}'}


def label(value):
    return ''.join(SYMBOLS.get(char, r'\\' if char == '\n' else tex(char)) for char in value)


def midpoint(points):
    lengths = [math.hypot(b[0]-a[0], b[1]-a[1]) for a,b in zip(points, points[1:])]
    remaining = sum(lengths) / 2
    for a,b,length in zip(points, points[1:], lengths):
        if length and remaining <= length:
            ratio = remaining / length
            return a[0]+ratio*(b[0]-a[0]), a[1]+ratio*(b[1]-a[1])
        remaining -= length
    return points[-1]


def render(scene):
    if not isinstance(scene, dict) or not isinstance(scene.get('parts'), list):
        raise ValueError('Scene must be an object containing a parts array.')
    width = number(scene.get('w'), 'scene width', 1)
    height = number(scene.get('h'), 'scene height', 1)
    colors = {}
    def color(value):
        if value == 'none':
            return 'none'
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            raise ValueError('Scene colors must be #RRGGBB or none.')
        if value not in colors:
            colors[value] = f'c{len(colors)}'
        return colors[value]

    drawing = [rf'\path[use as bounding box] (0,0) rectangle ({width},{height});']
    for part in scene['parts']:
        validate_part(part)
        kind = part['kind']
        dashed = ',dashed' if part.get('dash') else ''
        if kind == 'line':
            options = [f'draw={color(part["color"])}', f'line width={part["sw"]}pt',
                       'line cap=round', 'line join=round']
            start = '{Stealth[length=5pt]}' if part.get('start') else ''
            end = '{Stealth[length=5pt]}' if part.get('arrow') else ''
            if start or end:
                options.append(start + '-' + end)
            points = ' -- '.join(f'({x},{y})' for x,y in part['points'])
            drawing.append(r'\draw[' + ','.join(options) + dashed + '] ' + points + ';')
            if part.get('label'):
                x,y = midpoint(part['points'])
                drawing.append(rf'\node[fill=white,text=black,inner sep=2pt,align=center,'
                               rf'font=\fontsize{{10}}{{12}}\selectfont] at ({x},{y}) '
                               + '{' + label(part['label']) + '};')
            continue
        x,y,w,h = (part[key] for key in ('x','y','w','h'))
        if kind == 'text':
            size = part['size']
            alignment = part.get('align', 'center')
            anchor = {'left': 'west', 'right': 'east'}.get(alignment, 'center')
            px = x if alignment == 'left' else (x+w if alignment == 'right' else x+w/2)
            font = rf'\fontsize{{{size}}}{{{size*1.1}}}\selectfont' + (r'\bfseries' if part.get('bold') else '')
            text_color = color(part['color'])
            text_style = 'text opacity=0,text=black' if text_color == 'none' else f'text={text_color}'
            options = f'anchor={anchor},align={alignment},inner sep=0pt,text width={w}pt,{text_style},font={{{font}}}'
            drawing.append(rf'\node[{options}] at ({px},{y+h/2}) {{{label(part["text"])}}};')
        else:
            options = f'fill={color(part["fill"])},draw={color(part["stroke"])},line width={part["sw"]}pt' + dashed
            if kind == 'rect':
                if part.get('radius'):
                    options += f',rounded corners={part["radius"]}pt'
                shape = f'({x},{y}) rectangle ({x+w},{y+h})'
            else:
                shape = f'({x+w/2},{y+h/2}) ellipse [x radius={w/2}pt,y radius={h/2}pt]'
            drawing.append(rf'\path[{options}] {shape};')
    lines = [r'\documentclass{article}', r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}',
             r'\usepackage{lmodern,tikz,amssymb}', r'\usetikzlibrary{arrows.meta}',
             rf'\usepackage[paperwidth={width+6}pt,paperheight={height+6}pt,margin=3pt]{{geometry}}',
             r'\pagestyle{empty}\setlength{\parindent}{0pt}\renewcommand{\familydefault}{\sfdefault}']
    for value,name in colors.items():
        lines.append(rf'\definecolor{{{name}}}{{HTML}}{{{value[1:]}}}')
    lines += [r'\begin{document}\noindent\begin{tikzpicture}[x=1pt,y=-1pt]', *drawing,
              r'\end{tikzpicture}\end{document}']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='A scene JSON file or a directory of scene JSON files')
    parser.add_argument('--output', type=Path, required=True, help='Output folder for TeX and PDF figures')
    parser.add_argument('--pdf', action='store_true', help='Compile with the available system pdflatex')
    args = parser.parse_args()
    try:
        files = [args.source] if args.source.is_file() else sorted(args.source.glob('*.json'))
        if not files or any(source.suffix.lower() != '.json' for source in files):
            raise ValueError('Supply a scene JSON file or a directory containing JSON scenes.')
        rendered = [(source.stem + '.tex', render(read_json(source))) for source in files]
        args.output.mkdir(parents=True, exist_ok=True)
        for filename, document in rendered:
            (args.output / filename).write_text(document, encoding='utf-8')
            if args.pdf:
                compile_pdf(args.output, filename)
        print(f'Rendered {len(files)} scene(s) into {args.output}')
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
