---
name: excalidraw-diagram
description: Create or edit Excalidraw diagrams that make visual arguments. Use when the user wants to visualize workflows, architectures, or concepts, or to change an existing .excalidraw file.
---

# Excalidraw Diagram Creator

Generate `.excalidraw` files that **argue visually**. A diagram isn't formatted text - it shows relationships and causality that words can't.

**Colors, fonts and background live in `references/color-palette.md`.** Read it before generating anything and use it as the only source of color. Everything else here is universal.

**Setup:** see `README.md`.

## Two tests

- **Isomorphism** - strip the text out. Does the structure still communicate?
- **Education** - could someone learn something concrete, or does it just label boxes?

## Step 1: pick the depth

**Conceptual** - abstract shapes for mental models and philosophies, where the concept *is* the abstraction.

**Technical** - real systems, protocols, architectures, anything that teaches. Research the actual specs first: real event names, real API methods, real payload shapes. Then include **evidence artifacts** - a code snippet, a JSON payload, a UI mockup, a named event sequence. Show what things look like, not just what they're called.

> Bad: `Protocol` → `Frontend`
> Good: `AG-UI streams RUN_STARTED, STATE_DELTA` → `createA2UIMessageRenderer()`

Technical diagrams work at three zoom levels at once: a summary flow across the top or bottom, labeled section boundaries that group components, and evidence inside each section.

## Step 2: map each concept to a pattern

Every major concept gets a *different* pattern. No card grids, no rows of equal boxes.

| If the concept... | Pattern |
|-------------------|---------|
| Spawns many outputs | Fan-out - arrows radiating from one source |
| Combines inputs | Convergence - arrows merging into one |
| Has hierarchy | Tree - trunk line, branch lines, free text |
| Is a sequence | Timeline - line, small dots, labels beside each |
| Loops | Cycle - arrow returning to the start |
| Is ambient state | Cloud - overlapping ellipses |
| Transforms | Assembly line - before → process → after |
| Compares | Side-by-side with visual contrast |
| Separates phases | A gap, or a dashed divider |

Lines plus free text beat boxes plus contained text nearly every time.

## Step 3: cut the containers

Default to free-floating text. A box earns its place only when it's a focal point, an arrow binds to it, or the shape itself means something (a diamond is a decision). Everything else - labels, descriptions, section titles, annotations - is typography.

**Aim for under 30% of text elements inside containers.**

| Concept | Shape |
|---------|-------|
| Labels, titles, detail | none |
| Timeline marker | 12px ellipse |
| Start, end, external system | ellipse |
| Decision | diamond |
| Process, component | rectangle |
| Hierarchy node | lines + text |

## Step 4: style

Engineering whiteboard: white canvas, hand-drawn strokes, black outlines, light fills. It should look like a sketch an engineer drew to explain a system, not a marketing graphic. No glow, no accent-coloured title words. Pull every color from the palette. Use the dark variant only when asked.

| Setting | Value |
|---------|-------|
| `roughness` | `1` on shapes, arrows and lines |
| `opacity` | `100` - always. Hierarchy comes from color and scale |
| `fontFamily` | `5` (Excalifont) for titles, section titles, box labels and short arrow labels. `6` (Nunito) for multi-line notes and list items. `3` for code |
| `strokeWidth` | `1` hairlines and dividers, `2` shapes and arrows, `4` the one main flow line |
| `roundness` | `{"type": 3}` on rectangles |

Apply one font rule across the whole diagram. A list that mixes Excalifont and Nunito items reads as a mistake.

**Every color has one meaning, and the legend says what it is.** Decide the encodings before you draw:

- **Arrow color = what flows over that hop**, for example the credential it carries. Line style can add one more meaning, such as dashed for an API call.
- **Box fill = who owns or runs the component.**
- **Box outline = status**, for example orange for "changes in this proposal".
- **Text color = status**, for example red for a risk, green for something that holds, orange for an open question.

Never reuse a color for a second meaning, not even in another section. The same hop must get the same color in every section. If "today" and "proposed" both draw caller to gateway, both use one color. Put every encoding in a legend on the canvas: arrows, boxes, line styles, text. If a color is not in the legend, remove it or add it to the legend.

**Scale carries hierarchy:** hero 300×150, primary 180×90, secondary 120×60, marker 12×12. Font sizes: 36 title, 24 section, 16 body, 13 annotation.

**Whitespace carries importance.** The most important element gets 200px+ of clear space. Guide the eye left→right or top→bottom.

**Every relationship needs an arrow.** Proximity is not a connection.

## Step 5: write skeletons, then expand

Write each element with only the fields that carry meaning, then let `diagram.py expand` fill in the rest. It adds seeds, versions and the Step 4 styling, turns `label` into bound text, binds arrows on both ends, and draws an arrow between two outlines when you give it `from` and `to`. A skeleton is about an eighth the size of the full JSON. See `references/element-templates.md`.

```bash
D=~/.claude/skills/excalidraw-diagram/references/diagram.py
uv run --script $D expand path/to/file.excalidraw
```

1. Write the wrapper (`type`, `version`, `appState`, `files`) and the elements. A large diagram can still go one section per edit.
2. Use descriptive ids (`gateway`, `arrow_fan_left`). A label becomes `<id>_label`.
3. A field you write always wins. Expand only fills what's missing, so set colors, `strokeStyle` and `fontSize` yourself.
4. Run expand after every edit. It's safe to repeat, and it never touches a field that's already there. It refuses to write if a binding is broken and says how to fix it.

Never write `seed`, `version`, `versionNonce` or `boundElements` by hand, and don't write a generator script per diagram. Expand is the generator.

To review the structure, run `uv run --script $D read path/to/file.excalidraw`. It prints one line per element with labels folded in. Don't read the raw JSON.

## Step 6: render and fix (mandatory)

You cannot judge a diagram from JSON.

The renderer sits beside this file, not in the working directory, so use its full path:

```bash
uv run --script ~/.claude/skills/excalidraw-diagram/references/render_excalidraw.py path/to/file.excalidraw \
  --output "$SCRATCH/file.png"
```

That validates every binding first, then writes the PNG. The PNG is for your own check, not a deliverable, so write it to your scratchpad directory (or `$TMPDIR`), never next to the `.excalidraw` file, and do not hand it to the user. Read the PNG. Then:

1. **Against your design** - does the structure match what you planned? Does each section use its intended pattern? Does the eye flow the way you wanted?
2. **Against defects** - clipped or overlapping text, arrows crossing elements or landing in empty space, floating labels, uneven spacing, cramped sections beside empty ones, text too small to read.
3. **Fix, expand, re-render.** Widen containers, adjust coordinates, add waypoints to arrow `points` to route around obstacles. Labels follow a moved shape, but arrows don't. Delete an arrow's `x`, `y` and `points` and expand redraws it.

Two to four passes is normal. Stop when you'd show it to someone without caveats - not at the first pass with no critical bugs.

## Step 7: open it in the browser

Hand the user the diagram as an editable canvas, not a picture:

```bash
uv run --script ~/.claude/skills/excalidraw-diagram/references/open_excalidraw.py path/to/file.excalidraw
```

The script validates the file, serves it on `127.0.0.1`, and opens the Excalidraw editor in the default browser, fitted to the window. "Save to file" or Cmd/Ctrl+S writes the edits back to the same `.excalidraw` file. It serves until stopped, so run it in the background and tell the user the URL it prints.

To see what the user changed, save a summary before opening and diff it after they save:

```bash
uv run --script $D read path/to/file.excalidraw > "$SCRATCH/before.txt"
# ...after the user saves:
uv run --script $D read path/to/file.excalidraw | diff "$SCRATCH/before.txt" -
```

The editor code loads from esm.sh, but the diagram stays on the machine. This is the default way to hand over a diagram. Give the user a PNG only when they ask for one.

## Editing an existing diagram

1. Run `diagram.py read` on the file. That summary is your view of the diagram, so don't read the raw JSON.
2. Each element sits on one line of the file, so edit it by id with the Edit tool. Add new elements as skeletons.
3. Run expand, then render and look, as in Step 6. The user's layout stays where they put it, because expand only fills missing fields.

## Checklist

- Real specs researched, evidence artifacts included (technical diagrams)
- Each major concept uses a different pattern
- Under 30% of text in containers
- Every relationship has an arrow
- Colors all from the palette, `roughness: 1`, `opacity: 100`
- Each color has one meaning across the whole diagram, and an on-canvas legend covers all of them
- `fontFamily: 5` for titles and labels, `6` for notes and lists, `3` for code
- Built from skeletons and `diagram.py expand`, with no hand-written seeds or `boundElements`
- Rendered to the scratchpad, viewed, and iterated on
- Opened in the browser with `open_excalidraw.py`, no PNG handed over

## References

- `references/color-palette.md` - colors, fonts, background
- `references/element-templates.md` - skeleton per element type
- `references/diagram.py` - expand, read, check
- `references/json-schema.md` - Excalidraw format
