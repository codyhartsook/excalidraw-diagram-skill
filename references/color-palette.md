# Color Palette & Brand Style

Single source of truth for colors. Light engineering whiteboard by default, for Kubernetes and agentic infrastructure. The values are Excalidraw's own palette, so the diagram matches what a person picks in the editor. A dark variant is at the end. Use it only when asked.

## Canvas

| Property | Value |
|----------|-------|
| `viewBackgroundColor` | `#ffffff` |
| `appState.ambientGlow` | `false` |

## Text

| Level | Color | Use for |
|-------|-------|---------|
| Title | `#1e1e1e` | Headings, box labels |
| Body | `#495057` | Descriptions, arrow labels |
| Muted | `#868e96` | Dates, sources, footnotes |

Titles stay black. Status colors (below) are the only colored text.

## Status colors

These are the colors that carry meaning. Give each one exactly one meaning per diagram and name it in the legend.

| Status | Arrow and outline | Text | Typical meaning |
|--------|-------------------|------|-----------------|
| Risk, leak, deny | `#e03131` | `#e03131` | a problem in today's system |
| Holds, allowed | `#2f9e44` | `#2f9e44` | something that is safe or works |
| Proposed, open | `#f08c00` | `#e8590c` | new in this proposal, or undecided |
| Neutral flow | `#1e1e1e` | | a hop that carries nothing special |
| API or control call | `#868e96`, dashed, `strokeWidth: 1` | | a side call, not the main path |

## Shapes

Black outline, light fill. The fill says who owns or runs the component. The outline stays black unless it carries a status.

| Purpose | Stroke | Fill |
|---------|--------|------|
| Control plane | `#1e1e1e` | `#d0ebff` |
| Data plane, gateway, tunnel | `#1e1e1e` | `#c5f6fa` |
| Agent or other untrusted code | `#1e1e1e` | `#e5dbff` |
| Kubernetes resource, API service | `#326ce5` | `#ffffff` |
| External, outside the cluster | `#1e1e1e` | `#f8f9fa` |
| Risk source | `#e03131` | `#fff5f5` |
| Open decision (diamond) | `#e8590c` | `#fff4e6` |
| Changed by the proposal | `#e8590c` outline on the owner's fill | |

Trust boundary, such as a sandbox: `#6741d9`, `strokeStyle: "dashed"`, `transparent` fill. Inactive or planned: neutral stroke, dashed, `transparent` fill.

## Structure

| Element | Value |
|---------|-------|
| Section | stroke `#adb5bd`, `transparent` fill, `strokeWidth: 1` |
| Hairline, divider, sub-boundary | `#adb5bd`, `strokeWidth: 1` |
| Connector from evidence to what it describes | `#adb5bd`, `strokeStyle: "dotted"` |
| Step marker | white circle, `#1e1e1e` stroke, black number |
| Timeline dot | `#1e1e1e`, or a status color for an event that matters |

## Legend

Every diagram that uses status colors or more than one fill carries a legend near the title. Group it by encoding: "Arrows: what the hop carries", "Boxes: who runs it", then one line for text colors. Draw each swatch with the same stroke, width and style as in the diagram.

## Evidence artifacts

Code and data blocks: background `#f8f9fa`, stroke `#ced4da`, `fontFamily: 3`. Syntax colors carry no meaning. Say so in the legend when the diagram also uses status colors.

| Token | Color |
|-------|-------|
| Keys, identifiers | `#1971c2` |
| Strings, values | `#9c36b5` |
| Numbers, booleans | `#2f9e44` |
| Comments | `#868e96` |

## Dark variant (only on request)

Canvas `#0e1320`, and the renderer adds an ambient glow unless `ambientGlow: false`. Text `#f2f5fa`, body `#9aa5b8`, muted `#7b8798`. Shapes use a dark fill and a saturated stroke: control plane `#8b5cf6` on `#242047`, data plane `#3b82f6` on `#162747`, agent `#a78bfa` on `#2a2947`, Kubernetes `#38bdf8` on `#163247`, allow `#34d399` on `#153636`, warning `#fbbf24` on `#2a2820`, deny `#fb7185` on `#392432`, external `#94a3b8` on `#262d3b`. Sections and hairlines `#2a3344`. Code blocks `#0a0e15`. Use `roughness: 0` and `fontFamily: 2` in this variant. The one-meaning-per-color and legend rules still apply.
