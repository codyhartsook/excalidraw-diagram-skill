# Color Palette

The only source of color. The look is a technical design doc: light gray canvas, white boxes with black outlines, and a few saturated colors that each carry one meaning. The values are Excalidraw's own palette, so they match what a person picks in the editor.

Canvas: `viewBackgroundColor: "#f8f9fa"`.

## Text

| Color | Use for |
|-------|---------|
| `#1e1e1e` | Titles, box labels, code |
| `#495057` | Notes, descriptions, arrow labels |
| `#868e96` | Captions, legend text, code comments |

Meaning colors (below) are the only other text colors.

## Meaning colors

Each diagram decides what these mean and says so in its legend. The meanings here are the usual ones.

| Color | Arrows and lines | Text and outlines | Usual meaning |
|-------|------------------|-------------------|---------------|
| Green | `#2f9e44` | `#2f9e44` | The safe path, verified behavior |
| Red | `#e03131` | `#e03131` | Risk, a leak, a denial |
| Orange | `#f08c00` | `#e8590c` | Proposed, new, or still open |
| Black | `#1e1e1e` | | A neutral hop, lifecycle order |
| Gray, dashed, `strokeWidth: 1` | `#868e96` | | A side call, such as an API call |
| Light gray, dotted, `strokeWidth: 1` | `#adb5bd` | | Points from evidence to what it describes |

`strokeWidth: 4` marks the hops that carry what the diagram is about, such as the token in a token-flow diagram. Every other arrow is `2`.

## Shapes

| Element | Stroke | Fill |
|---------|--------|------|
| Component | `#1e1e1e` | `#ffffff` |
| Proposed or changed component | `#e8590c` | `#ffffff` |
| Planned for later | `#868e96`, label in `#868e96` | `#ffffff` |
| Trust boundary, such as a sandbox | `#6741d9`, dashed | `transparent` |
| Section, host or pod boundary | `#adb5bd`, `strokeWidth: 1` | `transparent` |
| Span or state bar | `#868e96`, `strokeWidth: 1` | `#e9ecef` |
| Step marker | `#1e1e1e`, number inside | `#ffffff` |
| Timeline dot | `#1e1e1e` | `#1e1e1e` |
| Code block | `#ced4da`, `strokeWidth: 1` | `#f8f9fa` |

## Code

`fontFamily: 3`, 13px, left-aligned. Code is `#1e1e1e` and comments are `#868e96`. No syntax highlighting, because color carries meaning everywhere else.

## Legend

Put the legend at the top right, beside the title. Group it by encoding: "Arrows: what the hop carries", then the box styles, then one line for text colors. Draw each swatch with the same stroke, width and style it has in the diagram.
