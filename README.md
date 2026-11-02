# rc505-drawio

Editable RC-505mkII resources for draw.io / diagrams.net, plus a Python script
that builds diagrams from JSON. Use complete panels, individual sections,
controls or LED variants. The generator accepts any compatible resource catalog;
its layout and rendering logic contain no preset-specific workflow.
A separate JSON-to-LaTeX generator creates illustrated tutorials using a shared
monochrome template.

## Open a library in draw.io

1. Save the [complete library XML](resources/library.xml) to your computer,
   or choose a section library from the table below.
2. Open a diagram in draw.io / diagrams.net and choose
   **File > Open Library from > Device**.
3. Select the downloaded `library.xml`. The library appears in the left panel;
   drag its elements onto the canvas.

For a local checkout, the complete file is `resources/library.xml` and section
libraries are under `resources/modules/<module>/library.xml`.
The [official draw.io guide](https://www.drawio.com/docs/manual/advanced/custom-shape-libraries/)
describes this import process.

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
| [Screen elements](resources/modules/screen-ui/library.xml) | 16 |
| [Gestures](resources/modules/gestures/library.xml) | 9 |
| [Generic interface elements](resources/modules/general-ui/library.xml) | 15 |
| [FX buttons](resources/modules/fx-buttons/library.xml) | 16 |

There are 109 resources across 12 modules. [Open the catalog](resources/catalog.drawio)
to browse their shapes together.

List the catalog's resource identifiers before referencing one in JSON:

```sh
python3 scripts/generate_diagram.py --list-resources
python3 scripts/generate_diagram.py --list-resources --module display-navigation
```

`--module` filters this list by the exact module name, such as `display-navigation`.

## Generate a diagram from JSON

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

## Generate a LaTeX tutorial

The [tutorial generator](scripts/generate_tutorial.py) uses a separate JSON content
format and the shared [LaTeX template](templates/tutorial.tex). It contains no
device settings or preset-specific procedure. It uses only the Python standard
library, just like the diagram generator.

```sh
python3 scripts/generate_tutorial.py examples/tutorial.json --output output/tutorial
python3 scripts/generate_tutorial.py examples/tutorial.json --output output/tutorial --pdf
```

The first command creates `main.tex`; `--pdf` also creates `main.pdf` using
`pdflatex`. Figures are copied into `images/`, so the output folder is a
self-contained LaTeX project. Edit the JSON for content and
`templates/tutorial.tex` for layout. Regeneration replaces `main.tex` and the
referenced images; preserve manual source edits before rebuilding.

### Tutorial content format

Start with [the text example](examples/tutorial.json). Required top-level fields
are `title` and a nonempty `pages` array. Optional fields are `author`, `eyebrow`
and `footer`. Each page needs `title` and nonempty `steps`; it may also contain
`intro`, `figure`, `notes` and `links`. Steps are numbered continuously.

| Step field | Content |
| --- | --- |
| `title` | Required short heading |
| `action` | Optional `press`, `twist`, `slide`, `connect` or `info`; the current template omits header icons |
| `route` | Menu labels, rendered with arrows |
| `access` | Physical-control figure showing how to reach a setting |
| `paragraphs`, `items` | Arrays of plain-text paragraphs or list items |
| `walkthrough` | 1–8 panels, each with `action`, optional `result`, `figure` and `screen` |
| `figure` | Main figure for this step |
| `table` | `headers` and `rows`, with 1–4 matching columns |
| `connections` | Abstract `[source, destination]` pairs |
| `knobs` | Up to four labels for generic rotary controls |
| `note` | Highlighted text |
| `links` | Objects containing `label` and a complete HTTP(S) `url` |

Figure objects use `path`, optional `height_mm` (5–100; default 45), `caption`
and `trim` (`[left, bottom, right, top]` in nonnegative PDF points).
Paths are relative to the content JSON file. Supported formats are PDF, PNG
and JPEG. `screen` uses the same figure format. Keep switch states as switches;
use `knobs` only for rotary controls.

Content is plain text, not Markdown or raw LaTeX. Special characters are
escaped. The template uses English typography and Latin fonts. Each page entry
starts a new page, but long content can spill onto additional pages: review the
rendered PDF and shorten or regroup steps as needed. The template is monochrome;
use monochrome figures, with color retained only where needed for LED states.

### Render kit elements as tutorial figures

[render_scenes.py](scripts/render_scenes.py) converts the same scene JSON files
used by the draw.io kit into editable TikZ/LaTeX and vector PDFs. It accepts
one scene file or a directory of scene files, without searching subdirectories.
For example, build the assets for the [illustrated example](examples/tutorial-illustrated.json):

```sh
python3 scripts/render_scenes.py resources/modules/display-navigation/scenes/menu-button.json --output build/figures --pdf
python3 scripts/render_scenes.py resources/modules/screen-ui/scenes/lcd-on-field.json --output build/figures --pdf
python3 scripts/generate_tutorial.py examples/tutorial-illustrated.json --output output/illustrated --pdf
```

Omit `--pdf` to produce only `.tex` files. To render a whole section, replace
the scene filename with its `scenes/` directory. Imported PDF figures exported
from draw.io can also be referenced directly; the renderer is optional.

### LaTeX requirements

Generating source needs only Python 3.9+. PDF compilation needs `pdflatex`
from TeX Live or MacTeX, on `PATH` or at `/Library/TeX/texbin/pdflatex`, plus
English Babel, Latin Modern, geometry, xcolor, TikZ, tabularx, array, enumitem,
fancyhdr, graphicx, tcolorbox and hyperref. The scene renderer also uses amssymb.
Compilation runs twice with shell escape disabled. The scripts do not install
packages or download resources.

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
