# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write, read and check .excalidraw files without handling the raw JSON by hand.

Usage:
    uv run diagram.py expand <file.excalidraw>  fill skeleton elements in place, derive bindings
    uv run diagram.py read <file.excalidraw>    one line per element, bound text folded into its container
    uv run diagram.py check <file.excalidraw>   validate ids and bindings on both ends
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_excalidraw import validate_excalidraw  # noqa: E402  (no Playwright needed)

DEFAULT_STROKE = "#1e1e1e"
SHAPES = ("rectangle", "ellipse", "diamond")
LABEL_PADDING = 5
CHAR_WIDTH = 0.55  # average glyph width per fontSize; only sizes free text, the render loop checks it

# Step 4 values. The renderer's own defaults differ (serif text, sharp corners), so write every one.
BASE = {
    "angle": 0, "strokeColor": DEFAULT_STROKE, "backgroundColor": "transparent", "fillStyle": "solid",
    "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
    "frameId": None, "roundness": None, "version": 1, "isDeleted": False, "boundElements": None,
    "link": None, "locked": False,
}
BY_TYPE = {
    "rectangle": {"roundness": {"type": 3}},
    "text": {"strokeWidth": 1, "fontSize": 16, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
             "containerId": None, "lineHeight": 1.25, "autoResize": True},
    "arrow": {"roundness": {"type": 2}, "startBinding": None, "endBinding": None, "startArrowhead": None,
              "endArrowhead": "arrow", "elbowed": False},
    "line": {"strokeWidth": 1, "roundness": {"type": 2}, "startBinding": None, "endBinding": None,
             "startArrowhead": None, "endArrowhead": None},
}


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: Invalid JSON in {path}: {e}")


def write_scene(path: Path, data: dict) -> None:
    """Write atomically, one element per line, so grep on an id returns the whole element."""
    rows = ",\n".join("    " + json.dumps(e, ensure_ascii=False) for e in data.get("elements", []))
    head = {k: v for k, v in data.items() if k not in ("elements", "appState", "files")}
    out = "{\n" + "".join(f"  {json.dumps(k)}: {json.dumps(v)},\n" for k, v in head.items())
    out += f'  "elements": [\n{rows}\n  ],\n'
    out += f'  "appState": {json.dumps(data.get("appState", {}), ensure_ascii=False)},\n'
    out += f'  "files": {json.dumps(data.get("files", {}))}\n}}\n'
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(out)
    os.replace(tmp, path)


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % 2_000_000_000  # stable, so expand is idempotent


def _text_size(text: str, font_size: float, line_height: float) -> tuple[float, float]:
    lines = text.split("\n")
    return max(len(line) for line in lines) * font_size * CHAR_WIDTH, len(lines) * font_size * line_height


def _center(el: dict) -> tuple[float, float]:
    return el["x"] + el["width"] / 2, el["y"] + el["height"] / 2


def _edge(el: dict, dx: float, dy: float, gap: float) -> tuple[float, float]:
    """Where a ray from el's center along (dx, dy) leaves its outline, plus a gap."""
    hw, hh = el["width"] / 2, el["height"] / 2
    if el["type"] == "ellipse":
        t = 1 / math.hypot(dx / hw, dy / hh)
    elif el["type"] == "diamond":
        t = 1 / (abs(dx) / hw + abs(dy) / hh)
    else:
        t = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
    cx, cy = _center(el)
    n = math.hypot(dx, dy)
    return cx + dx * t + dx / n * gap, cy + dy * t + dy / n * gap


def expand(data: dict) -> list[str]:
    """Fill missing fields, turn label/from/to into real elements and bindings. Never overwrites a given field."""
    errors: list[str] = []
    out: list[dict] = []
    for el in data.get("elements", []):
        if not el.get("id") or not el.get("type"):
            errors.append(f"element without id or type: {json.dumps(el)[:80]}")
            continue
        label = el.pop("label", None)
        out.append(el)
        if label is not None:
            spec = label if isinstance(label, dict) else {"text": label}
            out.append({"type": "text", "id": f"{el['id']}_label", "containerId": el["id"],
                        "textAlign": "center", "verticalAlign": "middle", **spec})
    data["elements"] = out

    for el in out:
        for key, value in {**BASE, **BY_TYPE.get(el["type"], {})}.items():
            el.setdefault(key, value)
        el.setdefault("seed", _seed(el["id"]))
        el.setdefault("versionNonce", _seed(el["id"] + "#nonce"))
        if el["type"] == "text":
            el.setdefault("originalText", el.get("text", ""))

    by_id = {e["id"]: e for e in out}

    # Arrows: from/to become bindings, and a straight path between the outlines when none is given.
    for el in out:
        ends = [el.pop("from", None), el.pop("to", None)]
        if not any(ends):
            continue
        for key, target in zip(("startBinding", "endBinding"), ends):
            if target is None:
                continue
            if target not in by_id:
                errors.append(f"{el['id']}: {'from' if key == 'startBinding' else 'to'} names missing element '{target}'")
                continue
            el[key] = {"elementId": target, "focus": 0, "gap": 4}
        if "points" not in el and all(t in by_id for t in ends):
            a, b = by_id[ends[0]], by_id[ends[1]]
            (ax, ay), (bx, by) = _center(a), _center(b)
            sx, sy = _edge(a, bx - ax, by - ay, 4)
            ex, ey = _edge(b, ax - bx, ay - by, 4)
            el.update(x=sx, y=sy, points=[[0, 0], [ex - sx, ey - sy]], width=abs(ex - sx), height=abs(ey - sy))
    for el in out:
        if el["type"] in ("arrow", "line"):
            el.setdefault("points", [[0, 0], [el.get("width", 0), el.get("height", 0)]])
            xs, ys = [p[0] for p in el["points"]], [p[1] for p in el["points"]]
            el.setdefault("width", max(xs) - min(xs))
            el.setdefault("height", max(ys) - min(ys))

    # Text: size free text, keep bound labels centred on their container.
    for el in out:
        if el["type"] != "text":
            continue
        w, h = _text_size(el.get("text", ""), el["fontSize"], el["lineHeight"])
        container = by_id.get(el["containerId"])
        if container is None:
            el.setdefault("width", w)
            el.setdefault("height", h)
            continue
        if container["type"] in ("arrow", "line"):
            pts = container["points"]
            cx, cy = container["x"] + (pts[0][0] + pts[-1][0]) / 2, container["y"] + (pts[0][1] + pts[-1][1]) / 2
        else:
            cx, cy = _center(container)
            el.setdefault("width", container["width"] - 2 * LABEL_PADDING)
        el.setdefault("width", w)
        el.setdefault("height", h)
        el.setdefault("x", cx - el["width"] / 2)
        el.setdefault("y", cy - el["height"] / 2)
        # A moved container leaves its label behind; the editor's own saves stay within a pixel.
        tx, ty = _center(el)
        # Arrow labels are skipped: Excalidraw places those itself and saves a stale position.
        centred = container["type"] in SHAPES and el["textAlign"] == "center" and el["verticalAlign"] == "middle"
        if centred and (abs(tx - cx) > 1 or abs(ty - cy) > 1):
            el["x"] += cx - tx
            el["y"] += cy - ty

    # Bindings on both ends: keep valid entries, add missing ones, drop stale ones.
    wanted: dict[str, list[dict]] = {}
    for el in out:
        refs = [(el.get(k) or {}).get("elementId") for k in ("startBinding", "endBinding")] + [el.get("containerId")]
        for target in dict.fromkeys(r for r in refs if r in by_id):
            wanted.setdefault(target, []).append({"id": el["id"], "type": el["type"]})
    for el in out:
        entries = wanted.get(el["id"], [])
        current = el.get("boundElements") or []
        if {b.get("id") for b in current} != {b["id"] for b in entries}:
            keep = [b for b in current if b.get("id") in {e["id"] for e in entries}]
            el["boundElements"] = keep + [e for e in entries if e["id"] not in {b.get("id") for b in keep}] or None

    for el in out:
        if "x" not in el or "y" not in el:
            errors.append(f"{el['id']}: needs x and y")
    return errors or validate_excalidraw(data)


def summarize(data: dict) -> str:
    """One stable line per element, sorted by id so two summaries diff cleanly."""
    elements = [e for e in data.get("elements", []) if not e.get("isDeleted")]
    by_id = {e.get("id"): e for e in elements}
    label_of = {e["containerId"]: e for e in elements if e.get("type") == "text" and e.get("containerId") in by_id}

    lines = [f"canvas {data.get('appState', {}).get('viewBackgroundColor', '#ffffff')}, {len(elements)} elements"]
    for el in sorted(elements, key=lambda e: str(e.get("id"))):
        if el.get("type") == "text" and el.get("containerId") in by_id:
            continue  # shown on its container's line
        kind = el.get("type")
        parts = [str(el.get("id")), kind]
        if kind in ("arrow", "line"):
            ends = [(el.get(k) or {}).get("elementId") for k in ("startBinding", "endBinding")]
            if any(ends):
                parts.append(f"{ends[0] or '.'} -> {ends[1] or '.'}")
        parts.append(f"{round(el.get('x', 0))},{round(el.get('y', 0))} {round(el.get('width', 0))}x{round(el.get('height', 0))}")
        if kind == "text":
            parts.append(f"{el.get('fontSize')}px {json.dumps(el.get('text', ''))}")
        elif el.get("id") in label_of:
            parts.append(json.dumps(label_of[el["id"]].get("text", "")))
        if el.get("strokeColor") not in (None, DEFAULT_STROKE):
            parts.append(f"stroke={el['strokeColor']}")
        if el.get("backgroundColor") not in (None, "transparent"):
            parts.append(f"fill={el['backgroundColor']}")
        if el.get("strokeStyle") not in (None, "solid"):
            parts.append(el["strokeStyle"])
        lines.append(" ".join(parts))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read or check an .excalidraw file")
    parser.add_argument("command", choices=["expand", "read", "check"])
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"ERROR: {args.input} does not exist")
    data = load(args.input)

    if args.command == "read":
        print(summarize(data))
        return

    if args.command == "expand":
        errors = expand(data)
        if not errors:
            write_scene(args.input, data)
    else:
        errors = validate_excalidraw(data)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
