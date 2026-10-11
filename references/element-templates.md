# Element Templates

Skeletons for each element type. Write only these fields, then run `diagram.py expand`. It fills in everything else with the Step 4 styling: `roughness: 1`, Excalifont, black stroke, white fill on shapes, rounded rectangles. Pull colors from `color-palette.md` by semantic purpose. Any field you add, such as `strokeStyle` or `fontFamily`, overrides the default.

## Free-floating text

```json
{"type": "text", "id": "title", "x": 80, "y": 30, "text": "Tool call authorization", "fontSize": 36}
```

Multi-line notes use `\n`, `"fontFamily": 6` and `"strokeColor": "#495057"`. Code uses `"fontFamily": 3`.

## Shape with a label

`label` becomes a bound text element named `<id>_label`, centred in the shape. Use a string, or an object to set the text's own fields.

```json
{"type": "rectangle", "id": "gateway", "x": 340, "y": 150, "width": 180, "height": 100, "label": "Gateway"}
{"type": "diamond", "id": "policy", "x": 640, "y": 140, "width": 160, "height": 120, "strokeColor": "#e8590c", "label": {"text": "Allowed?", "fontSize": 13}}
```

`ellipse` works the same way. Add `"code": "repo:path#symbol"` to link a shape to the code it stands for. See "Linking boxes to code" in `SKILL.md`.

## Arrow

`from` and `to` bind both ends. Without `points`, expand draws a straight arrow between the two outlines. To route around something, give `x`, `y` and `points` yourself. `points` are relative to `x`/`y`, and the first point is `[0, 0]`.

```json
{"type": "arrow", "id": "client_to_gateway", "from": "client", "to": "gateway", "label": "JWT"}
{"type": "arrow", "id": "side_call", "from": "gateway", "to": "idp", "strokeColor": "#868e96", "strokeStyle": "dashed", "strokeWidth": 1}
```

## Line (structure, not connection)

Trunks, timelines, dividers. The default is a hairline (`strokeWidth: 1`).

```json
{"type": "line", "id": "divider", "x": 80, "y": 320, "points": [[0, 0], [480, 0]], "strokeColor": "#adb5bd", "strokeStyle": "dashed"}
```

## Marker dot

```json
{"type": "ellipse", "id": "dot1", "x": 94, "y": 94, "width": 12, "height": 12, "backgroundColor": "#1e1e1e", "strokeWidth": 1}
```

## Section boundary

A hairline rectangle with no fill, plus a free-floating label above its top-left corner.

```json
{"type": "rectangle", "id": "section1", "x": 60, "y": 160, "width": 620, "height": 380, "strokeColor": "#adb5bd", "strokeWidth": 1, "backgroundColor": "transparent"}
```

## Evidence artifact (code or JSON)

A light block with left-aligned monospace text on top, in `#1e1e1e` with comments in `#868e96`. Keep it to 6 lines or fewer.

```json
{"type": "rectangle", "id": "code_bg", "x": 100, "y": 600, "width": 420, "height": 150, "strokeColor": "#ced4da", "backgroundColor": "#f8f9fa", "strokeWidth": 1}
{"type": "text", "id": "code_keys", "x": 116, "y": 616, "text": "{\n  \"tool\": \"search\",\n  \"sub\": \"agent-7\"\n}", "fontFamily": 3, "fontSize": 13}
```
