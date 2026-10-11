---
name: excalidraw-diagram
description: Create or edit Excalidraw diagrams that make visual arguments. Use when the user wants to visualize workflows, architectures, or concepts, or to change an existing .excalidraw file.
---

# Excalidraw Diagram Creator

Generate `.excalidraw` files that **argue visually**. A diagram isn't formatted text - it shows relationships and causality that words can't.

**Colors, fonts and background live in `references/color-palette.md`.** Read it before generating anything and use it as the only source of color. Everything else here is universal.

**Setup:** rendering needs a headless browser. Run this once: `uv run --script ~/.claude/skills/excalidraw-diagram/references/render_excalidraw.py --install`.

## Two tests

- **Isomorphism** - strip the text out. Does the structure still communicate?
- **Education** - could someone learn something concrete, or does it just label boxes?

## Step 1: pick the depth

**Conceptual** - abstract shapes for mental models and philosophies, where the concept *is* the abstraction.

**Technical** - real systems, protocols, architectures, anything that teaches. Research the actual specs first: real event names, real API methods, real payload shapes. Then include **evidence artifacts** - a code snippet, a JSON payload, a UI mockup, a named event sequence. Show what things look like, not just what they're called.

> Bad: `Protocol` → `Frontend`
> Good: `AG-UI streams RUN_STARTED, STATE_DELTA` → `createA2UIMessageRenderer()`

When the diagram documents code you can read, link its boxes to that code. See "Linking boxes to code".

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

Technical design doc: light gray canvas, white boxes, black outlines, hand-drawn strokes. It should look like a sketch an engineer drew to explain a system, not a marketing graphic. No accent-coloured title words. Pull every color from the palette.

| Setting | Value |
|---------|-------|
| `roughness` | `1` on shapes, arrows and lines |
| `opacity` | `100` - always. Hierarchy comes from color and scale |
| `fontFamily` | `5` (Excalifont) for titles, section titles, box labels and short arrow labels. `6` (Nunito) for multi-line notes and list items. `3` for code |
| `strokeWidth` | `1` hairlines and dividers, `2` shapes and arrows, `4` the hops that carry what the diagram is about |
| `roundness` | `{"type": 3}` on rectangles |

Apply one font rule across the whole diagram. A list that mixes Excalifont and Nunito items reads as a mistake.

**Every color has one meaning, and the legend says what it is.** Decide the encodings before you draw:

- **Arrow color = what flows over that hop**, for example the credential it carries. Line style can add one more meaning, such as dashed for an API call.
- **Box outline = status**, for example orange for "changes in this proposal". Boxes stay white, and a dashed purple outline marks a trust boundary.
- **Text color = status**, for example red for a risk, green for something that holds, orange for an open question.

Never reuse a color for a second meaning, not even in another section. The same hop must get the same color in every section. If "today" and "proposed" both draw caller to gateway, both use one color. Put every encoding in a legend on the canvas: arrows, boxes, line styles, text. If a color is not in the legend, remove it or add it to the legend.

**Scale carries hierarchy:** hero 300×150, primary 180×90, secondary 120×60, marker 12×12. Font sizes: 36 title, 24 section, 16 labels and body, 13 notes and legend. The section the diagram is about can go up to 20 for labels and 18 for notes.

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

## Linking boxes to code

When a diagram documents code, each box that stands for a function, type, service or file carries a `code` ref. Expand turns it into a clickable GitHub link, `diagram.py check` fails when the code moves out from under it, and the editor opens it in VS Code.

```json
{"type": "rectangle", "id": "invoice_gen", "x": 0, "y": 0, "width": 180, "height": 80, "label": "Invoice Generator", "code": "billing:src/invoice.ts#generateInvoice"}
```

The form is `repo:path#symbol`. The path is relative to the repo root, and the symbol is optional.

1. **Find the checkouts.** For each repo the diagram covers, find its local checkout and read the code before you link it. Ask the user for any repo you can't find.
2. **Write `diagram.repos.toml`** next to the diagram, or in a parent directory, and commit it with the diagram. It maps each repo id to GitHub. `git remote get-url origin` gives the repo, and `git symbolic-ref --short refs/remotes/origin/HEAD` gives the branch. Don't assume `main`. Keep repo ids short and lowercase, one per repo, and reuse an existing file's ids.

    ```toml
    [billing]
    github = "acme/billing-api"
    branch = "main"
    ```

3. **Map the checkouts** in `~/.config/diagram-links/local.toml`, which is per machine and never committed. Without it, check can't verify a ref, links have no line, and the editor can't open VS Code. Ask before writing it, because it's the user's machine config. If they decline, write the same content to your scratchpad and set `DIAGRAM_LOCAL_CONFIG` to that file for every `diagram.py` and `open_excalidraw.py` call.

    ```toml
    billing = "~/src/billing-api"
    ```

4. **Add the refs.** On a new element, put `code` in the skeleton. On an existing element, add `"code": "..."` to its line by id with the Edit tool. Expand moves it into `customData`. Pick the symbol a reader would open first: the constructor, handler, or exported function that does what the box says. Use its exact name from the file, never a name from memory.
5. **Expand, then check.** Expand writes the GitHub links at the symbol's line on the linked branch, as of the last `git fetch`. Check names each box whose file or symbol is gone, for example `"Invoice Generator" points to generateInvoice, which is not defined in src/invoice.ts`. Fix every failure. Repos it lists as not checked have no entry in `local.toml`.

Rules:

- Link only code that exists. A box for planned work stays unlinked until the code lands. Say so in its label or a note.
- An evidence block that names a source file doesn't replace a ref. Put the ref on the box the evidence describes.
- Don't link arrows, sections or free text. Link the boxes.

When you hand over a linked diagram, tell the user how to use the editor from Step 7:

- **Cmd+click** (Ctrl+click off macOS) on a linked box opens its code in VS Code at the line, or on GitHub when the repo isn't in `local.toml`.
- **Shift+Cmd+click** opens VS Code's diff of that file against where the branch split off.
- Both open in the VS Code window that has the repo, so its language tooling works. Hovering a box shows what each one does.

Both need the `code` command on PATH. In VS Code, run "Shell Command: Install 'code' command in PATH" once. The diff needs the repo in `local.toml` and a file that changed since the checkout split off `origin/<branch>`. Otherwise the hover hint leaves the diff out. Run `git fetch` first so the split point is current.

When the user asks for one box's code or diff in the terminal, run the same commands the editor runs. Use the box's ref and the branch from `diagram.repos.toml`:

```bash
cd ~/src/billing-api                      # the checkout from local.toml
code .                                    # focus the window that has the repo
code --reuse-window --goto src/invoice.ts:42
base=$(git merge-base origin/main HEAD)
git show "$base:src/invoice.ts" > "$SCRATCH/invoice.ts" 2>/dev/null   # empty when the branch added the file
code --reuse-window --diff "$SCRATCH/invoice.ts" src/invoice.ts      # left: split point, right: working file
```

For another editor, such as the VS Code extension, `uv run --script $D links path/to/file.excalidraw -o "$SCRATCH/walk.excalidraw"` writes a copy with `vscode://` links. The committed file keeps its GitHub links.

## Checklist

- Real specs researched, evidence artifacts included (technical diagrams)
- Each major concept uses a different pattern
- Under 30% of text in containers
- Every relationship has an arrow
- Colors all from the palette, `roughness: 1`, `opacity: 100`
- Each color has one meaning across the whole diagram, and an on-canvas legend covers all of them
- `fontFamily: 5` for titles and labels, `6` for notes and lists, `3` for code
- Built from skeletons and `diagram.py expand`, with no hand-written seeds or `boundElements`
- Boxes that stand for code carry a `code` ref, and `diagram.py check` passes
- Rendered to the scratchpad, viewed, and iterated on
- Opened in the browser with `open_excalidraw.py`, no PNG handed over

## References

- `references/color-palette.md` - colors, fonts, background
- `references/element-templates.md` - skeleton per element type
- `references/diagram.py` - expand, read, check, links
- `references/json-schema.md` - Excalidraw format
