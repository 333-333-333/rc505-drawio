# Resource provenance

These are original editable vector drawings of RC-505mkII controls and reusable diagram elements. The repository contains static scene data, SVGs and native draw.io shapes. It does not include the source photographs, manuals, tutorial content or a preset-specific setup. BOSS and Roland names identify the depicted equipment.

## Organization and identifiers

The catalog contains 107 unique resources across 12 modules. Each module has its own `library.xml`, `scenes/` and `svg/`; the root `library.xml` contains all resources. `catalog.drawio` has five category pages: hardware, connections/cables, actions, LED variants and LCD/generic controls.

| Module | Resources | Purpose |
| --- | ---: | --- |
| `device` | 3 | Assembled top, rear and compact block |
| `input-fx` | 1 | Input FX section |
| `track-fx` | 2 | Track FX section and bank-selection action |
| `fx-buttons` | 16 | Shared A–D LED variants for both FX sections |
| `tracks` | 12 | Reusable track strip, buttons, LEDs and actions |
| `display-navigation` | 10 | Display, encoders, navigation and menu routes |
| `global-controls` | 4 | Global transport and ALL START/STOP variants |
| `rhythm` | 1 | Rhythm controls |
| `connections` | 20 | Rear sections, cable edges and connectors |
| `gestures` | 9 | Press, hold, twist and slide symbols |
| `screen-ui` | 14 | LCD components, templates and reference screens |
| `general-ui` | 15 | Generic controls and indicators |

Named scenes retain their existing stable IDs. Remaining IDs use deterministic title slugs. Content is deduplicated independently of its title; this export has no aliases or slug collisions. The shared `fx-buttons` module avoids duplicating the same A–D geometry in two libraries. Human-readable titles are metadata; references should use catalog IDs.

## Hardware geometry

Top-panel proportions and control centers were measured from the [official front photograph](https://static.roland.com/assets/images/articles/thumbnails/rc-505mk2_F_gal.jpg), at 1680 × 920 pixels. Its SHA-256 is `80908616f829a507388a3e0b0059dbb564d083228d8fc84cdad194b7998c17e1`.

The assembled top keeps that aspect ratio, at a width of 780 drawing units. Sections and derived zooms preserve the same calibrated geometry. Manual photo measurements have an estimated tolerance of ±3 source pixels for centers and ±5 pixels for bounds. This is visual calibration, not a mechanical drawing or a dimensional specification.

Rear-port order and button shapes were checked against the [Owner's Manual](https://static.roland.com/assets/media/pdf/RC-505mk2_eng03_W.pdf), pages 4–6. Rear views face the connectors: SUB2, SUB1 and MAIN have L/MONO above R; INST2 and INST1 have R left of L/MONO. Rear section widths are schematic; the order and pair orientation are preserved.

## LED variants

The Owner's Manual, pages 4–5 and 9–11, documents A–D red for an enabled effect, pink for the enabled effect being edited, off for a disabled effect, and blue for the current bank during bank selection. Only LED outlines use color. RGB values are illustrative interpretations of those color names.

For track FX, TRACK and ALL START/STOP, colored variants are explicitly named `photo-appearance`: the official photograph shows red FX, green TRACK and green ALL START/STOP. The manual does not establish those hues as universal state mappings. Neutral lit/unlit variants are also available. Dashed outlines represent blinking as a diagram convention. STOP blinking for current-track indication is documented in the [system program 1.30 release notes](https://www.boss.info/global/support/by_product/rc-505mk2/updates_drivers/5c6ad538-d4c8-4187-8a4b-384b7117061c/); its hue is unspecified.

The [Parameter Guide](https://static.roland.com/assets/media/pdf/RC-505mk2_Parameter_eng04_W.pdf), pages 14–16 and 33, documents configurable LED behavior in specific contexts. The REC/PLAY status palette is not generalized to all hardware buttons. Press and hold are gestures, not LED states.

## LCD references

LCD resources use a 512 × 256 drawing frame, preserving the 128:64 display aspect ratio. All components remain editable. Editorial captions were removed from the resources and recorded here instead.

`menu-screen`, `menu-setup-screen`, `setup-screen` and `setup-autooff-screen` reproduce the field labels and example values shown in the Owner's Manual, page 17. Their symbols and rendering are simplified vector references, not pixel-exact firmware screenshots. SETUP values such as `7`, `MEMORY NUMBER`, `POS+STATUS`, `IMMEDIATE`, `ON`, `01` and `99` are manual examples; they do not describe the user's current settings. Page-arrow and selection treatments are schematic.

The four-column template `title-schematic-screen-reference` uses explicit `TITLE`, `LABEL` and `VALUE` placeholders. Separate headers, fields, cursors, menu items and ON/OFF fields support new screens. Preset-specific target values and the tutorial's four-cable setup are excluded.

## Physical actions and validation limits

The eight `action-*` resources depict reusable physical operations. Menu routes identify the label below which to press a knob without inventing an unverified selector number. CTL FUNC navigation says to continue until the option appears. Track clearing requires holding that track's STOP button for at least two seconds. Track 5 selection depicts the physical press; custom assignments can alter its behavior.

Bank selection is sequential: hold the right-hand TRACK FX EDIT until the current bank button turns blue, press C, then press EDIT to finish. It is not an EDIT+C chord. C is blue only in the selection panel; the final LED state is not asserted. These operations were checked against the Owner's Manual, pages 5, 7–8, 11, 14 and 16–17.

Validation covers JSON/SVG/XML structure, unique IDs, cell references, module counts, content deduplication, preserved source geometry and native cable edges. The resources have not been imported through the draw.io GUI or exercised on physical hardware.
