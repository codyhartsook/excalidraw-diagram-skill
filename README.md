# Excalidraw Diagram Skill

A coding agent skill that generates Excalidraw diagrams from natural language. Not boxes and arrows - diagrams that **argue visually**.

Works with any agent that reads `~/.claude/skills/`. SKILL.md calls its scripts from that path.

## What it does

- **Argues, not displays.** Each concept gets the pattern that mirrors its behaviour: fan-out for one-to-many, timelines for sequences, convergence for aggregation. No card grids.
- **Evidence artifacts.** Technical diagrams carry real code snippets and real payloads, not boxes labelled "API Response".
- **Sees its own output.** A Playwright render pipeline turns the file into a PNG so the agent can catch overlaps, clipping and bad arrow routing, then fix them in a loop.
- **Engineering whiteboard by default.** White canvas, hand-drawn strokes, black outlines, light fills. Every color has one meaning and appears in an on-canvas legend. A dark variant with an ambient glow is available on request. All of it in one file.

## Install

```bash
git clone https://github.com/coleam00/excalidraw-diagram-skill.git
cp -r excalidraw-diagram-skill ~/.claude/skills/excalidraw-diagram
```

## Setup

One command, once - it installs the headless browser. Python dependencies are declared inline in the script.

```bash
uv run --script ~/.claude/skills/excalidraw-diagram/references/render_excalidraw.py --install
```

## Use

> "Diagram how agentgateway authorizes an MCP tool call across the control plane and data plane"

The skill handles concept mapping, layout, JSON, rendering and visual validation.

## Render on its own

```bash
uv run --script references/render_excalidraw.py diagram.excalidraw
```

Validates the file first - a binding pointing at a missing element fails before the browser opens. Writes a PNG next to the input.

## Open it in the browser

```bash
uv run --script references/open_excalidraw.py diagram.excalidraw
```

Opens an editable Excalidraw canvas served from 127.0.0.1. "Save to file" (or Cmd/Ctrl+S) writes your edits back to the `.excalidraw` file. The editor loads from esm.sh, and the diagram is never uploaded.

## Customize

Edit `references/color-palette.md`. It holds every color, the canvas, and the text hierarchy. The ambient glow lives in `references/render_template.html` and switches off per file with `appState.ambientGlow: false`.

## Files

```
SKILL.md                     Design method and workflow
references/
  color-palette.md           Colors and canvas - edit this
  element-templates.md       Skeleton per element type
  diagram.py                 Expand skeletons, summarize, check bindings
  json-schema.md             Excalidraw format
  render_excalidraw.py       Validate and render to PNG
  render_template.html       Browser-side render, background, glow
  open_excalidraw.py         Serve an editable canvas on 127.0.0.1
  editor_template.html       Browser-side editor
```
