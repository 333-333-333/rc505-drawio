#!/usr/bin/env python3
"""Check or format uncompressed draw.io models and XML shape libraries."""
import argparse
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / 'resources'


def finite(value, name, nonnegative=False):
    try:
        parsed = float(value) if not isinstance(value, bool) else float('nan')
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'{name} must be a finite number.') from error
    if not math.isfinite(parsed) or (nonnegative and parsed < 0):
        raise ValueError(f'{name} must be finite' + (' and nonnegative.' if nonnegative else '.'))


def parse_xml(text):
    try:
        return ET.fromstring(text, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    except ET.ParseError as error:
        raise ValueError(f'Malformed XML: {error}') from error


def validate_model(model):
    if model.tag != 'mxGraphModel' or model.find('root') is None:
        raise ValueError('Expected mxGraphModel with a root element.')
    elements = list(model.iter())
    identities = [element.get('id') for element in elements if 'id' in element.attrib]
    if any(not identity for identity in identities) or len(identities) != len(set(identities)):
        raise ValueError('Model IDs must be nonempty and unique.')
    owners = {child: parent for parent in elements for child in parent}
    cells = list(model.iter('mxCell'))
    if not cells:
        raise ValueError('Model must contain mxCell elements.')
    known = set()
    for cell in cells:
        identity = cell.get('id')
        wrapper = owners[cell]
        if (not identity and wrapper.tag in ('object', 'UserObject')
                and owners.get(wrapper) is model.find('root')
                and len(wrapper.findall('mxCell')) == 1):
            identity = wrapper.get('id')
        if not identity:
            raise ValueError('Each mxCell needs an ID, directly or on its immediate object/UserObject wrapper.')
        known.add(identity)
    for cell in cells:
        for name in ('parent', 'source', 'target'):
            if name in cell.attrib and cell.get(name) not in known:
                raise ValueError(f'Unknown {name} reference: {cell.get(name)}')
    for element in elements:
        names = ('x', 'y', 'width', 'height') if element.tag in ('mxGeometry', 'mxPoint', 'mxRectangle') else ()
        if element is model:
            names = ('pageWidth', 'pageHeight', 'dx', 'dy', 'gridSize', 'scale', 'border')
        for name in names:
            if name in element.attrib:
                finite(element.get(name), name, name in ('width', 'height', 'pageWidth', 'pageHeight', 'gridSize', 'scale', 'border'))


def serialize(root, declaration=False):
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=declaration).decode('utf-8') + '\n'


def invalid_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')


def canonicalize(text):
    root = parse_xml(text)
    if root.tag == 'mxlibrary':
        try:
            entries = json.loads(root.text or '', parse_constant=invalid_constant)
        except json.JSONDecodeError as error:
            raise ValueError(f'Malformed library JSON: {error}') from error
        if not isinstance(entries, list):
            raise ValueError('mxlibrary must contain a JSON array.')
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get('xml'), str):
                raise ValueError(f'Library entry {index} needs an uncompressed xml string; image entries are unsupported.')
            if not entry['xml'].lstrip().startswith('<'):
                raise ValueError(f'Library entry {index}: compressed XML is unsupported; save uncompressed XML.')
            for name in ('w', 'h'):
                if not isinstance(entry.get(name), (int, float)):
                    raise ValueError(f'Library entry {index} requires numeric {name}.')
                finite(entry[name], f'library {name}', True)
            model = parse_xml(entry['xml'])
            validate_model(model)
            entry['xml'] = serialize(model).rstrip('\n')
        content = json.dumps(entries, ensure_ascii=False, indent=2, allow_nan=False)
        root.text = '\n' + '\n'.join('  ' + line for line in content.splitlines()) + '\n'
    elif root.tag == 'mxfile':
        diagrams = root.findall('diagram')
        if not diagrams:
            raise ValueError('mxfile must contain a diagram.')
        page_ids = [diagram.get('id') for diagram in diagrams if 'id' in diagram.attrib]
        if any(not page_id for page_id in page_ids) or len(page_ids) != len(set(page_ids)):
            raise ValueError('Diagram IDs must be nonempty and unique within mxfile.')
        for diagram in diagrams:
            models = diagram.findall('mxGraphModel')
            if len(models) != 1:
                raise ValueError('Each diagram needs one uncompressed mxGraphModel; compressed diagrams are unsupported.')
            validate_model(models[0])
    elif root.tag == 'mxGraphModel':
        validate_model(root)
    else:
        raise ValueError(f'Unsupported XML root: {root.tag}; expected mxlibrary, mxfile or mxGraphModel.')
    return serialize(root, declaration=True)


def collect_paths(paths):
    found = set()
    for path in paths:
        if not path.exists():
            raise ValueError(f'Path does not exist: {path}')
        candidates = path.rglob('*') if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in ('.xml', '.drawio'):
                found.add(candidate.resolve())
            elif not path.is_dir():
                raise ValueError(f'Unsupported file extension: {candidate}')
    if not found:
        raise ValueError('No .xml or .drawio files found.')
    return sorted(found)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', type=Path, nargs='*', help='Files or directories; defaults to repository resources/')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Check validity and canonical two-space formatting (default)')
    mode.add_argument('--fix', action='store_true', help='Rewrite valid files with canonical two-space formatting')
    args = parser.parse_args(argv)
    failures = 0
    try:
        paths = collect_paths(args.paths or [DEFAULT_ROOT])
    except ValueError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    for path in paths:
        try:
            original = path.read_bytes().decode('utf-8')
            formatted = canonicalize(original)
            if original != formatted:
                if not args.fix:
                    raise ValueError('Noncanonical formatting; run with --fix.')
                with path.open('w', encoding='utf-8', newline='\n') as stream:
                    stream.write(formatted)
            print(f'OK {path}')
        except (OSError, UnicodeError, ValueError) as error:
            failures += 1
            print(f'Error: {path}: {error}', file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
