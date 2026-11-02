#!/usr/bin/env python3
"""Generate editable draw.io diagrams from a JSON specification and resource catalog."""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / 'resources' / 'catalog.json'


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'{path}: {error}') from error


def keys(value, allowed, context):
    if not isinstance(value, dict):
        raise ValueError(f'{context} must be an object.')
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f'{context}: unknown fields: {", ".join(sorted(unknown))}')


def number(value, context, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (minimum is not None and value < minimum):
        suffix = '' if minimum is None else f' >= {minimum}'
        raise ValueError(f'{context} must be a finite number{suffix}.')
    return value


def pair(value, context, minimum=0):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f'{context} must contain two numbers.')
    return [number(v, context, minimum) for v in value]


def string(value, context):
    if not isinstance(value, str):
        raise ValueError(f'{context} must be text.')
    return value


def load_catalog(path):
    data = read_json(path)
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1 or not isinstance(data.get('resources'), dict):
        raise ValueError('Catalog must contain version: 1 and a resources object.')
    return data['resources'], path.resolve().parent


def validate_part(part):
    if not isinstance(part, dict) or part.get('kind') not in ('rect', 'ellipse', 'text', 'line'):
        raise ValueError('Resource primitive must be rect, ellipse, text or line.')
    kind = part['kind']
    if kind == 'line':
        points = part.get('points')
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError('Line primitive requires at least two coordinate pairs.')
        for point in points:
            pair(point, 'line point', None)
        number(part.get('sw'), 'line stroke width')
        string(part.get('color'), 'line color')
        string(part.get('label', ''), 'line label')
        return
    for key in ('x', 'y'):
        number(part.get(key), f'primitive {key}', None)
    for key in ('w', 'h'):
        number(part.get(key), f'primitive {key}', .001)
    if kind == 'text':
        number(part.get('size'), 'font size', .001)
        string(part.get('text'), 'primitive text')
        string(part.get('color'), 'text color')
        if part.get('align', 'center') not in ('left', 'center', 'right'):
            raise ValueError('Text alignment must be left, center or right.')
    else:
        number(part.get('sw'), 'stroke width')
        number(part.get('radius', 0), 'corner radius')
        string(part.get('fill'), 'fill color')
        string(part.get('stroke'), 'stroke color')


def screen_scene(screen):
    keys(screen, ['title', 'fields', 'selected'], 'screen')
    title = string(screen.get('title', ''), 'screen.title')
    fields = screen.get('fields', [])
    if not isinstance(fields, list) or not 1 <= len(fields) <= 4:
        raise ValueError('screen.fields must contain 1-4 label/value objects.')
    selected = screen.get('selected')
    if selected is not None and (type(selected) is not int or not 0 <= selected < len(fields)):
        raise ValueError('screen.selected must be a zero-based field index.')
    parts = [dict(kind='rect', x=0, y=0, w=512, h=256, fill='#000000', stroke='#000000', radius=0, sw=1)]
    def text(value, x, y, w, h, size, color='#FFFFFF'):
        parts.append(dict(kind='text', text=value, x=x, y=y, w=w, h=h,
                          size=size, color=color, bold=True, align='center'))
    text(title, 10, 5, 492, 35, 22)
    parts.append(dict(kind='line', points=[[8, 45], [504, 45]], color='#FFFFFF', sw=1,
                      arrow=False, start=False, dash=False, label=''))
    for index, field in enumerate(fields):
        keys(field, ['label', 'value'], f'screen.fields[{index}]')
        label = string(field.get('label', ''), 'field.label')
        value = string(field.get('value', ''), 'field.value')
        x = index * 128
        if selected == index:
            parts.append(dict(kind='rect', x=x+5, y=65, w=118, h=75,
                              fill='#FFFFFF', stroke='none', radius=0, sw=0))
        text(value, x+7, 70, 114, 65, 18, '#000000' if selected == index else '#FFFFFF')
        text(label, x+7, 170, 114, 70, 16)
    return dict(title=title, w=512, h=256, parts=parts)


def resource_scene(step, catalog, root):
    if ('resource' in step) == ('screen' in step):
        raise ValueError('Each step needs exactly one of resource or screen.')
    if 'screen' in step:
        scene = screen_scene(step['screen'])
    else:
        resource_id = string(step['resource'], 'step.resource')
        if resource_id not in catalog:
            raise ValueError(f'Unknown resource: {resource_id}. Use --list-resources.')
        source = (root / catalog[resource_id]['path']).resolve()
        if not source.is_relative_to(root):
            raise ValueError(f'Resource path escapes catalog directory: {resource_id}')
        scene = read_json(source)
    number(scene.get('w'), 'resource width', 1)
    number(scene.get('h'), 'resource height', 1)
    if not isinstance(scene.get('parts'), list):
        raise ValueError('Resource must contain a parts array.')
    for part in scene['parts']:
        validate_part(part)
    scene = copy.deepcopy(scene)
    replacements = step.get('text', {})
    if not isinstance(replacements, dict):
        raise ValueError('step.text must map existing text to replacement text.')
    found = set()
    for part in scene['parts']:
        if part.get('kind') == 'text' and part.get('text') in replacements:
            old = part['text']
            part['text'] = string(replacements[old], f'text replacement for {old}')
            found.add(old)
    if found != set(replacements):
        raise ValueError(f'Text not found in resource: {", ".join(sorted(set(replacements)-found))}')
    return scene


def vertex(root, cell_id, parent, value, style, x, y, w, h):
    cell = ET.SubElement(root, 'mxCell', id=cell_id, parent=parent, vertex='1', value=value, style=style)
    ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as': 'geometry'})
    return cell


def primitive(root, cell_id, parent, part, scale, dx, dy):
    kind = part.get('kind')
    if kind == 'line':
        points = part['points']
        if len(points) < 2:
            raise ValueError('Line primitive requires at least two points.')
        style = (f'strokeColor={part["color"]};strokeWidth={part["sw"]*scale};'
                 f'endArrow={"block" if part.get("arrow") else "none"};'
                 f'startArrow={"block" if part.get("start") else "none"};dashed={int(bool(part.get("dash")))};')
        cell = ET.SubElement(root, 'mxCell', id=cell_id, parent=parent, edge='1', value=part.get('label', ''), style=style)
        geometry = ET.SubElement(cell, 'mxGeometry', relative='1', attrib={'as': 'geometry'})
        transformed = [(dx+x*scale, dy+y*scale) for x,y in points]
        for point,name in [(transformed[0], 'sourcePoint'), (transformed[-1], 'targetPoint')]:
            ET.SubElement(geometry, 'mxPoint', x=str(point[0]), y=str(point[1]), attrib={'as': name})
        if len(transformed) > 2:
            waypoints = ET.SubElement(geometry, 'Array', attrib={'as': 'points'})
            for x,y in transformed[1:-1]:
                ET.SubElement(waypoints, 'mxPoint', x=str(x), y=str(y))
        return
    if kind == 'text':
        style = (f'text;html=0;whiteSpace=wrap;overflow=hidden;strokeColor=none;fillColor=none;'
                 f'fontFamily=Helvetica;fontSize={part["size"]*scale};fontColor={part["color"]};'
                 f'fontStyle={int(bool(part.get("bold")))};align={part.get("align", "center")};verticalAlign=middle;')
        value = part['text']
    elif kind in ('rect', 'ellipse'):
        style = (f'shape={"rectangle" if kind == "rect" else "ellipse"};'
                 f'fillColor={part["fill"]};strokeColor={part["stroke"]};strokeWidth={part["sw"]*scale};')
        if part.get('radius'):
            style += f'rounded=1;absoluteArcSize=1;arcSize={part["radius"]*scale*2};'
        value = ''
    else:
        raise ValueError(f'Unsupported resource primitive: {kind}')
    vertex(root, cell_id, parent, value, style, dx+part['x']*scale, dy+part['y']*scale,
           part['w']*scale, part['h']*scale)


def page_model(page, inherited_layout, catalog, resource_root):
    keys(page, ['title', 'steps', 'edges', 'layout'], 'page')
    layout = dict(inherited_layout)
    keys(page.get('layout', {}), ['columns', 'cell_width', 'cell_height', 'gap', 'margin'], 'layout')
    layout.update(page.get('layout', {}))
    columns = layout.get('columns', 2)
    if type(columns) is not int or columns < 1:
        raise ValueError('layout.columns must be a positive integer.')
    cw = number(layout.get('cell_width', 360), 'layout.cell_width', 60)
    ch = number(layout.get('cell_height', 260), 'layout.cell_height', 60)
    gap = number(layout.get('gap', 32), 'layout.gap')
    margin = number(layout.get('margin', 40), 'layout.margin')
    steps = page.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ValueError('Every page needs a nonempty steps array.')
    model = ET.Element('mxGraphModel', grid='1', gridSize='10', page='1')
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    title = string(page.get('title', ''), 'page.title')
    if title:
        vertex(root, 'heading', '1', title, 'text;html=0;align=left;fontSize=24;fontStyle=1;whiteSpace=wrap;', margin, margin, columns*cw+(columns-1)*gap, 36)
    seen, right, bottom = set(), 400, 300
    for index, step in enumerate(steps):
        keys(step, ['id', 'resource', 'screen', 'title', 'caption', 'at', 'size', 'text'], f'steps[{index}]')
        node_id = string(step.get('id'), 'step.id')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', node_id) or node_id in seen:
            raise ValueError(f'Duplicate or invalid step id: {node_id}')
        seen.add(node_id)
        x,y = pair(step.get('at', [margin+(index % columns)*(cw+gap), margin+(50 if title else 0)+(index // columns)*(ch+gap)]), 'step.at')
        w,h = pair(step.get('size', [cw,ch]), 'step.size', 60)
        scene = resource_scene(step, catalog, resource_root)
        heading = string(step.get('title', ''), 'step.title')
        caption = string(step.get('caption', ''), 'step.caption')
        top = 36 if heading else 10
        footer = 42 if caption else 10
        if h <= top + footer:
            raise ValueError(f'Step {node_id} is too short for its title and caption.')
        scale = min((w-20)/scene['w'], (h-top-footer)/scene['h'])
        dx,dy = (w-scene['w']*scale)/2, top+(h-top-footer-scene['h']*scale)/2
        parent = 'node-' + node_id
        vertex(root, parent, '1', '', 'group;', x,y,w,h)
        if heading:
            vertex(root, f'title-{index}', parent, heading, 'text;html=0;align=left;fontSize=16;fontStyle=1;whiteSpace=wrap;', 5,0,w-10,32)
        for part_index, part in enumerate(scene['parts']):
            primitive(root, f'part-{index}-{part_index}', parent, part, scale, dx, dy)
        if caption:
            vertex(root, f'caption-{index}', parent, caption, 'text;html=0;align=left;fontSize=12;whiteSpace=wrap;', 5,h-37,w-10,32)
        right,bottom = max(right,x+w+margin),max(bottom,y+h+margin)
    edges = page.get('edges', [])
    if not isinstance(edges, list):
        raise ValueError('page.edges must be an array.')
    for index, edge in enumerate(edges):
        keys(edge, ['from', 'to', 'label', 'points'], f'edges[{index}]')
        if edge.get('from') not in seen or edge.get('to') not in seen:
            raise ValueError('Each edge must reference existing step ids in its page.')
        label = string(edge.get('label', ''), 'edge.label')
        cell = ET.SubElement(root, 'mxCell', id=f'edge-{index}', parent='1', edge='1',
                             source='node-'+edge['from'], target='node-'+edge['to'], value=label,
                             style='edgeStyle=orthogonalEdgeStyle;endArrow=block;strokeColor=#000000;fontColor=#000000;labelBackgroundColor=#FFFFFF;')
        geometry = ET.SubElement(cell, 'mxGeometry', relative='1', attrib={'as':'geometry'})
        points = edge.get('points', [])
        if not isinstance(points, list):
            raise ValueError('edge.points must be an array of coordinate pairs.')
        if points:
            array = ET.SubElement(geometry, 'Array', attrib={'as':'points'})
            for point in points:
                px,py = pair(point, 'edge point')
                ET.SubElement(array, 'mxPoint', x=str(px), y=str(py))
                right,bottom = max(right,px+margin),max(bottom,py+margin)
    model.set('pageWidth', str(math.ceil(right)))
    model.set('pageHeight', str(math.ceil(bottom)))
    return model


def generate(spec, catalog, resource_root):
    keys(spec, ['title', 'steps', 'edges', 'layout', 'pages'], 'specification')
    layout = spec.get('layout', {})
    keys(layout, ['columns', 'cell_width', 'cell_height', 'gap', 'margin'], 'layout')
    if 'pages' in spec:
        if 'steps' in spec or 'edges' in spec:
            raise ValueError('Use either pages or top-level steps/edges, not both.')
        pages = spec['pages']
    else:
        pages = [{key:value for key,value in spec.items() if key != 'layout'}]
    if not isinstance(pages, list) or not pages:
        raise ValueError('pages must be a nonempty array.')
    book = ET.Element('mxfile', host='app.diagrams.net', type='device')
    for index,page in enumerate(pages, 1):
        model = page_model(page, layout, catalog, resource_root)
        diagram = ET.SubElement(book, 'diagram', id=f'page-{index}', name=page.get('title') or spec.get('title') or f'Page {index}')
        diagram.append(model)
    return ET.tostring(book, encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('specification', type=Path, nargs='?', help='UTF-8 JSON specification')
    parser.add_argument('-o', '--output', type=Path, help='Output file; defaults to the specification name with .drawio')
    parser.add_argument('--resources', type=Path, default=DEFAULT_CATALOG, help='Resource catalog JSON')
    parser.add_argument('--list-resources', action='store_true', help='List available resource ids and titles')
    parser.add_argument('--module', help='Filter --list-resources by module name')
    parser.add_argument('--validate', action='store_true', help='Validate without writing an output file')
    args = parser.parse_args()
    try:
        catalog, root = load_catalog(args.resources)
        if args.list_resources:
            for resource_id,entry in sorted(catalog.items()):
                if not args.module or entry.get('module') == args.module:
                    print(f'{resource_id}\t{entry["title"]}')
            return 0
        if args.specification is None:
            parser.error('specification is required unless --list-resources is used')
        data = generate(read_json(args.specification), catalog, root)
        if args.validate:
            print('Specification is valid.')
            return 0
        output = args.output or args.specification.with_suffix('.drawio')
        if output.resolve() == args.specification.resolve():
            raise ValueError('Output must not overwrite the specification.')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        print(output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
