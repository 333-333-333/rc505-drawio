# rc505-drawio

Editable RC-505mkII resources for draw.io / diagrams.net, plus a Python script
that builds diagrams from JSON. Use complete panels, individual sections,
controls or LED variants. The generator accepts any compatible resource catalog;
its layout and rendering logic contain no preset-specific workflow.

## Quick start

Requires **Python 3.9 or later**. The generator uses the Python standard library;
there are no packages to install or API keys to configure.

```sh
git clone https://github.com/333-333-333/rc505-drawio.git
cd rc505-drawio
python3 scripts/generate_diagram.py --list-resources
python3 scripts/generate_diagram.py examples/basic-flow.json -o output/basic-flow.drawio
```

Open the resulting `.drawio` file in draw.io / diagrams.net. Its parts, labels
and connectors remain editable. To validate without writing a file:

```sh
python3 scripts/generate_diagram.py examples/basic-flow.json --validate
```

Without `-o`, the output uses the specification's name and folder:

```sh
python3 scripts/generate_diagram.py examples/custom-screen.json
# Creates examples/custom-screen.drawio
```

## Use the libraries directly

In draw.io, choose **File > Open Library from > Device** and select a library
XML file. Drag individual resources onto the canvas. Load the
[complete library](resources/library.xml), or choose a module below.

| Module library | Resources |
| --- | ---: |
| [Display and navigation](resources/modules/display-navigation/library.xml) | 10 |
| [Tracks](resources/modules/tracks/library.xml) | 12 |
| [Complete device](resources/modules/device/library.xml) | 3 |
| [Input FX section](resources/modules/input-fx/library.xml) | 1 |
| [Track FX section](resources/modules/track-fx/library.xml) | 2 |
| [Global controls](resources/modules/global-controls/library.xml) | 4 |
| [Rhythm](resources/modules/rhythm/library.xml) | 1 |
| [Connections](resources/modules/connections/library.xml) | 20 |
| [Screen elements](resources/modules/screen-ui/library.xml) | 14 |
| [Gestures](resources/modules/gestures/library.xml) | 9 |
| [Generic interface elements](resources/modules/general-ui/library.xml) | 15 |
| [FX buttons](resources/modules/fx-buttons/library.xml) | 16 |

There are 107 resources across 12 modules. [Open the catalog](resources/catalog.drawio)
to browse their shapes together.

List the catalog's resource identifiers before referencing one in JSON:

```sh
python3 scripts/generate_diagram.py --list-resources
python3 scripts/generate_diagram.py --list-resources --module display-navigation
```

`--module` filters this list by the exact module name, such as `display-navigation`.

## Write a specification

The input is UTF-8 JSON, not natural-language instructions. The script does not
interpret prose or call a model. Start with one of these synthetic examples:

- [Basic flow](examples/basic-flow.json): catalog resources, exact text replacement and an edge.
- [Custom screen](examples/custom-screen.json): a generic panel with `LEVEL = 42` and `MODE = ON`.
- [Multiple pages](examples/multi-page.json): page-specific layout and explicit positioning.

The examples demonstrate the format. Their values do not describe a device setup.

For a single page, put `steps` and optional `edges` directly in the specification.
For several pages, use `pages`; do not also provide top-level `steps` or `edges`.
`title` names a single page, or supplies a fallback page name when using `pages`.

| Field | Meaning |
| --- | --- |
| `steps` | Nonempty list of resource or screen instances |
| `edges` | Optional connections between step IDs on the same page |
| `layout` | Optional defaults for the automatic grid |
| `pages` | Nonempty list of pages, each with `title`, `steps`, `edges` and/or `layout` |

Each step needs a unique `id` and **exactly one** of `resource` or `screen`:

| Step field | Meaning |
| --- | --- |
| `id` | Starts with a letter; remaining characters may be letters, digits, `_` or `-` |
| `resource` | An exact identifier from `--list-resources` |
| `screen` | A custom screen object, described below |
| `title` | Optional heading above this instance |
| `caption` | Optional short caption below it |
| `at` | Optional `[x, y]` position in page coordinates |
| `size` | Optional `[width, height]` fit box, including heading and caption |
| `text` | Optional map from existing text to replacement text |

### Grid and position

Steps follow their array order across the grid, then continue on the next row.
All dimensions are draw.io page units, normally pixels.

| Layout field | Default | Constraint |
| --- | --- | --- |
| `columns` | `2` | Positive integer |
| `cell_width` | `360` | At least `60` |
| `cell_height` | `260` | At least `60` |
| `gap` | `32` | Zero or greater |
| `margin` | `40` | Zero or greater |

A page's `layout` overrides the corresponding top-level defaults. A page title
reserves 50 units above the grid. Set `at` to position an instance explicitly;
other instances keep their automatic positions. The script does not move
neighboring steps to avoid overlap.

`size` replaces the grid cell's fit box for that instance. The resource scales
uniformly inside it, preserving its aspect ratio and leaving room for its title
and caption. Both dimensions must be at least 60; a title and caption together
require additional height. Page bounds expand to include instances and edge points.

### Replace labels

`text` matches complete existing strings, including case and line breaks. Every
matching text primitive is replaced. A missing source string is an error.
For example, the basic flow replaces the `MENU` label with `DEMO`. Replacement keeps the original font
and text box; keep labels short, use explicit line breaks, or edit the native
text in draw.io when a longer label needs more space.

### Connect steps

Each edge has `from` and `to` step IDs, an optional `label`, and optional
`points`: a list of `[x, y]` waypoints in page coordinates. Connections are
orthogonal arrows attached to the step groups. IDs must exist on that page;
cross-page edges are not supported. Coordinates must be finite and nonnegative.

```json
{"from": "first", "to": "second", "label": "Next", "points": [[420, 210]]}
```

### Create a screen

A `screen` has an optional `title`, a `fields` array containing one to four
objects, and an optional `selected` index. Each field has a text `label` and
text `value`. Use `"42"`, not `42`. `selected` is zero-based: `1` highlights the
second field. The generated screen is a generic editable monochrome panel.

```json
{"title": "EXAMPLE", "fields": [{"label": "LEVEL", "value": "42"}, {"label": "MODE", "value": "ON"}], "selected": 0}
```

## Use another catalog

Pass `--resources path/to/catalog.json`. Catalog version 1 maps resource IDs to
entries containing `title`, `category`, `path` and `module`:

```json
{"version": 1, "resources": {"example-control": {"title": "Example control", "category": "Controls", "path": "scenes/example.json", "module": "controls"}}}
```

Each `path` is relative to the catalog's directory and must stay inside it.
A scene contains numeric `w` and `h` dimensions plus a `parts` array using
`rect`, `ellipse`, `text` and `line` primitives. The included scene JSON files
show the primitive fields; paths do not depend on the current working directory.

## Errors and validation

Invalid input exits with a nonzero status and an error message. Checks include
unknown fields, duplicate/invalid step IDs, missing resources, unmatched label
replacements, invalid numbers, malformed screens, invalid edge targets and
paths escaping the catalog directory. `--validate` performs generation checks
without saving the diagram. An output path cannot overwrite its input JSON.

Validation constructs the same XML as generation. Review the
opened diagram for suitable spacing, readable labels and the intended workflow.

## Lint and format XML

The linter checks `.xml` and `.drawio` files, including XML models inside the
JSON payload of shape libraries. It validates unique IDs, cell references and
finite geometry, then checks canonical two-space formatting.

```sh
python3 scripts/lint_xml.py --check
python3 scripts/lint_xml.py --fix
python3 scripts/lint_xml.py --check output/basic-flow.drawio
```

With no paths, it checks `resources/`. Pass files or directories to check other
outputs. Compressed models and image-only library entries are not supported;
save uncompressed draw.io XML before linting them. This is a structural check,
not a complete implementation of the draw.io schema.

## Run the tests

```sh
python3 -m unittest discover -s tests -v
```
