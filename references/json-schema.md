# Excalidraw JSON Schema

## File wrapper

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [],
  "appState": { "viewBackgroundColor": "#ffffff", "gridSize": null, "ambientGlow": false },
  "files": {}
}
```

`appState.ambientGlow: false` turns off the renderer's background glow.

## Element types

| Type | Use for |
|------|---------|
| `rectangle` | Processes, components, section boundaries |
| `ellipse` | Entry and exit points, external systems, marker dots |
| `diamond` | Decisions |
| `arrow` | Connections |
| `line` | Trunks, timelines, dividers |
| `text` | Labels, free-floating or contained |
| `frame` | Grouping container (rarely needed - a hairline rectangle reads better) |

## Shared properties

| Property | Values |
|----------|--------|
| `id` | Unique string. Descriptive, e.g. `gateway_rect` |
| `x`, `y`, `width`, `height` | Pixels |
| `strokeColor`, `backgroundColor` | Hex, or `"transparent"` |
| `fillStyle` | `solid`, `hachure`, `cross-hatch` |
| `strokeWidth` | `1`, `2`, or `4` - no other values |
| `strokeStyle` | `solid`, `dashed`, `dotted` |
| `roughness` | `0` clean, `1` hand-drawn, `2` rough |
| `opacity` | `0`-`100` |
| `seed`, `versionNonce` | Any integer |
| `roundness` | `{"type": 3}` on shapes, `{"type": 2}` on lines and arrows, `null` for sharp |

## Text

| Property | Notes |
|----------|-------|
| `text`, `originalText` | Identical. Readable words only |
| `fontSize` | 13 annotation, 16 body, 24 section, 36 title |
| `fontFamily` | `5` Excalifont (hand-drawn), `6` Nunito, `3` monospace. Legacy: `1` Virgil, `2` Helvetica |
| `textAlign` | `left`, `center`, `right` |
| `verticalAlign` | `top`, `middle`, `bottom` |
| `containerId` | Parent shape id, or `null` |
| `lineHeight` | `1.25` |

## Arrows

| Property | Notes |
|----------|-------|
| `points` | `[[x, y], ...]` relative to the element's `x`/`y`. First point is `[0, 0]` |
| `startBinding`, `endBinding` | `{"elementId": "id", "focus": 0, "gap": 2}`, or `null` |
| `startArrowhead`, `endArrowhead` | `null`, `arrow`, `bar`, `dot`, `triangle` |
| `elbowed` | `true` for right-angle routing |

## Bindings

Both sides must agree. The arrow points at the shape through `startBinding`/`endBinding`; the shape points back through `boundElements`:

```json
"boundElements": [{"id": "arrow1", "type": "arrow"}, {"id": "text1", "type": "text"}]
```

`diagram.py expand` writes `boundElements` from the bindings, so you never edit it by hand. The renderer and `diagram.py check` fail the file when the two sides disagree.
