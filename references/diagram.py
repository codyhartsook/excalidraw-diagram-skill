# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write, read and check .excalidraw files without handling the raw JSON by hand.

Usage:
    uv run diagram.py expand <file.excalidraw>          fill skeletons in place, derive bindings and code links
    uv run diagram.py read <file.excalidraw>            one line per element, bound text folded into its container
    uv run diagram.py check <file.excalidraw>           validate bindings, and code refs that have a local checkout
    uv run diagram.py links <file.excalidraw> -o <out>  copy with vscode:// links for a walkthrough

Code refs live in customData.code as {repo, path, symbol}. diagram.repos.toml, next to the diagram
or in a parent directory, maps each repo id to GitHub. ~/.config/diagram-links/local.toml (or
$DIAGRAM_LOCAL_CONFIG) maps repo ids to local checkouts on this machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_excalidraw import validate_excalidraw  # noqa: E402  (no Playwright needed)

DEFAULT_STROKE = "#1e1e1e"
SHAPES = ("rectangle", "ellipse", "diamond")
LABEL_PADDING = 5
REPOS_FILE = "diagram.repos.toml"
LOCAL_CONFIG = "~/.config/diagram-links/local.toml"
DEFINITION = r"\b(?:def|class|func|function|fn|type|interface|struct|enum|const|let|var)\b.*"
CHAR_WIDTH = 0.55  # average glyph width per fontSize; only sizes free text, the render loop checks it

# Step 4 values. The renderer's own defaults differ (serif text, sharp corners), so write every one.
BASE = {
    "angle": 0, "strokeColor": DEFAULT_STROKE, "backgroundColor": "transparent", "fillStyle": "solid",
    "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
    "frameId": None, "roundness": None, "version": 1, "isDeleted": False, "boundElements": None,
    "link": None, "locked": False,
}
BY_TYPE = {
    "rectangle": {"backgroundColor": "#ffffff", "roundness": {"type": 3}},
    "ellipse": {"backgroundColor": "#ffffff"},
    "diamond": {"backgroundColor": "#ffffff"},
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


def parse_code(code: str | dict) -> dict:
    """"billing:src/invoice.ts#generateInvoice" -> {"repo", "path", "symbol"}."""
    if isinstance(code, dict):
        return code
    repo, _, rest = code.partition(":")
    path, _, symbol = rest.partition("#")
    return {"repo": repo, "path": path, **({"symbol": symbol} if symbol else {})}


def load_repos(diagram: Path) -> dict:
    for folder in diagram.resolve().parents:
        if (folder / REPOS_FILE).is_file():
            return tomllib.loads((folder / REPOS_FILE).read_text(encoding="utf-8"))
    return {}


def load_local() -> dict[str, Path]:
    path = Path(os.environ.get("DIAGRAM_LOCAL_CONFIG", LOCAL_CONFIG)).expanduser()
    if not path.is_file():
        return {}
    return {repo: Path(root).expanduser() for repo, root in tomllib.loads(path.read_text(encoding="utf-8")).items()}


def find_symbol(text: str, symbol: str) -> int | None:
    """Line of the symbol's definition, else its first mention. A grep, not a parser."""
    lines = text.splitlines()
    word = rf"\b{re.escape(symbol)}\b"
    for pattern in (re.compile(DEFINITION + word), re.compile(word)):
        for n, line in enumerate(lines, 1):
            if pattern.search(line):
                return n
    return None


def code_refs(data: dict) -> list[tuple[dict, dict]]:
    return [(e, e["customData"]["code"]) for e in data.get("elements", [])
            if not e.get("isDeleted") and isinstance((e.get("customData") or {}).get("code"), dict)]


def label_text(data: dict, el: dict) -> str:
    for t in data.get("elements", []):
        if t.get("type") == "text" and t.get("containerId") == el["id"] and not t.get("isDeleted"):
            return " ".join(t.get("text", "").split())
    return el.get("text") or el["id"]


def branch_text(root: Path, branch: str, path: str) -> str | None:
    """The file as the linked branch has it, from the checkout's last fetch."""
    shown = subprocess.run(["git", "-C", str(root), "show", f"origin/{branch}:{path}"], capture_output=True, text=True)
    return shown.stdout if shown.returncode == 0 else None


def resolve(ref: dict, repos: dict, local: dict[str, Path]) -> tuple[str | None, str | None, str | None, str | None]:
    """(GitHub link, vscode link, problem, note). Lines, problems and notes need a local checkout.

    The working tree decides problems and vscode lines. The linked branch decides the GitHub line,
    so a checkout on a feature branch still links to where the symbol is on that branch.
    """
    root, line, problem, note = local.get(ref["repo"]), None, None, None
    if root is not None:
        file = root / ref["path"]
        if not file.is_file():
            problem = f"{ref['path']} in {ref['repo']}, which does not exist"
        elif ref.get("symbol"):
            line = find_symbol(file.read_text(encoding="utf-8", errors="replace"), ref["symbol"])
            if line is None:
                problem = f"{ref['symbol']}, which is not defined in {ref['path']}"
    repo = repos.get(ref["repo"])
    github = None
    if repo:
        branch = repo.get("branch", "main")
        anchor = ""
        if root is not None and not problem:
            text = branch_text(root, branch, ref["path"])
            branch_line = find_symbol(text, ref["symbol"]) if text and ref.get("symbol") else None
            if text is None:
                note = f"{ref['path']} is not on origin/{branch}, so its GitHub link 404s until it merges"
            elif ref.get("symbol") and branch_line is None:
                note = f"{ref['symbol']} is not on origin/{branch} yet, so its GitHub link has no line"
            anchor = f"#L{branch_line}" if branch_line else ""
        github = f"https://github.com/{repo['github']}/blob/{branch}/{ref['path']}{anchor}"
    file_uri = (root / ref["path"]).resolve().as_posix().lstrip("/") if root and not problem else None
    vscode = f"vscode://file/{file_uri}{f':{line}' if line else ''}" if file_uri else None
    return github, vscode, problem, note


def apply_links(data: dict, diagram: Path, local_links: bool = False) -> list[str]:
    """Point each code-linked element's link at its code. Returns warnings, never fails."""
    refs = code_refs(data)
    if not refs:
        return []
    repos, local, warnings = load_repos(diagram), load_local(), []
    if not repos:
        warnings.append(f"no {REPOS_FILE} next to the diagram or above it, so code refs have no GitHub links")
    for el, ref in refs:
        github, vscode, problem, note = resolve(ref, repos, local)
        if note:
            warnings.append(f"{el['id']}: {note}")
        if repos and ref["repo"] not in repos:
            warnings.append(f"{el['id']}: repo '{ref['repo']}' is not in {REPOS_FILE}")
        if problem:
            warnings.append(f'"{label_text(data, el)}" points to {problem}')
        link = (vscode if local_links else None) or github
        if link:
            el["link"] = link
    return warnings


def check_code(data: dict, diagram: Path) -> tuple[list[str], list[str]]:
    """(errors, repos skipped for lack of a local checkout)."""
    repos, local, errors, skipped = load_repos(diagram), load_local(), [], set()
    if code_refs(data) and not repos:
        return [f"code refs need a {REPOS_FILE} next to the diagram or in a parent directory"], []
    for el, ref in code_refs(data):
        if ref["repo"] not in repos:
            errors.append(f"{el['id']}: repo '{ref['repo']}' is not in {REPOS_FILE}")
        if ref["repo"] not in local:
            skipped.add(ref["repo"])
            continue
        problem = resolve(ref, repos, local)[2]
        if problem:
            errors.append(f'"{label_text(data, el)}" points to {problem}')
    return errors, sorted(skipped)


def expand(data: dict) -> list[str]:
    """Fill missing fields, turn label/from/to into real elements and bindings. Never overwrites a given field."""
    errors: list[str] = []
    out: list[dict] = []
    for el in data.get("elements", []):
        if not el.get("id") or not el.get("type"):
            errors.append(f"element without id or type: {json.dumps(el)[:80]}")
            continue
        label = el.pop("label", None)
        code = el.pop("code", None)
        if code is not None:
            el["customData"] = {**(el.get("customData") or {}), "code": parse_code(code)}
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

    lines = [f"canvas {data.get('appState', {}).get('viewBackgroundColor', '#f8f9fa')}, {len(elements)} elements"]
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
        code = (el.get("customData") or {}).get("code")
        if isinstance(code, dict):
            parts.append(f"code={code.get('repo')}:{code.get('path')}" + (f"#{code['symbol']}" if code.get("symbol") else ""))
        lines.append(" ".join(parts))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read or check an .excalidraw file")
    parser.add_argument("command", choices=["expand", "read", "check", "links"])
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="links: where to write the local copy")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"ERROR: {args.input} does not exist")
    data = load(args.input)

    if args.command == "read":
        print(summarize(data))
        return

    if args.command == "links":
        if args.output is None or args.output.resolve() == args.input.resolve():
            sys.exit("ERROR: links needs -o <copy>; the committed diagram keeps its GitHub links")
        for warning in apply_links(data, args.input, local_links=True):
            print(f"  ! {warning}", file=sys.stderr)
        write_scene(args.output, data)
        print(args.output)
        return

    if args.command == "expand":
        errors = expand(data)
        if not errors:
            for warning in apply_links(data, args.input):
                print(f"  ! {warning}", file=sys.stderr)
            write_scene(args.input, data)
    else:
        errors = validate_excalidraw(data)
        code_errors, skipped = check_code(data, args.input)
        errors += code_errors
        if skipped:
            print(f"  not checked, no local checkout: {', '.join(skipped)}", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
