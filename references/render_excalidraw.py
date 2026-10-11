# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.49"]
# ///
"""Render Excalidraw JSON to PNG using Playwright + headless Chromium.

Usage:
    uv run render_excalidraw.py <path-to-file.excalidraw> [--output path.png] [--scale 2] [--width 1920]

First-time setup (installs the browser; dependencies come from the header above):
    uv run render_excalidraw.py --install
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def validate_excalidraw(data: dict) -> list[str]:
    """Validate Excalidraw JSON structure and references. Returns list of errors."""
    errors: list[str] = []

    if data.get("type") != "excalidraw":
        errors.append(f"Expected type 'excalidraw', got '{data.get('type')}'")

    if "elements" not in data:
        errors.append("Missing 'elements' array")
        return errors
    if not isinstance(data["elements"], list):
        errors.append("'elements' must be an array")
        return errors
    if not data["elements"]:
        errors.append("'elements' array is empty - nothing to render")
        return errors

    # Dangling references are the usual cost of hand-editing a diagram section by section.
    elements = [e for e in data["elements"] if not e.get("isDeleted")]
    by_id = {e.get("id"): e for e in elements}
    seen: set[str] = set()

    def lists(target: dict, eid: str) -> bool:
        return any(isinstance(b, dict) and b.get("id") == eid for b in target.get("boundElements") or [])

    def points_back(el: dict, target_id: str) -> bool:
        bindings = (el.get("startBinding"), el.get("endBinding"))
        return el.get("containerId") == target_id or any(
            isinstance(b, dict) and b.get("elementId") == target_id for b in bindings
        )

    # Both ends must agree, or the editor detaches arrows and the renderer drops bound text.
    for el in elements:
        eid = el.get("id", "<no id>")
        if eid in seen:
            errors.append(f"Duplicate element id: {eid}")
        seen.add(eid)

        targets = [(k, (el.get(k) or {}).get("elementId")) for k in ("startBinding", "endBinding")]
        targets.append(("containerId", el.get("containerId")))
        for key, tid in targets:
            if not tid:
                continue
            if tid not in by_id:
                errors.append(f"{eid}: {key} points at missing element '{tid}'")
            elif not lists(by_id[tid], eid):
                errors.append(
                    f"{eid}: {key} is '{tid}', but '{tid}' does not list it. "
                    f'Add {{"id": "{eid}", "type": "{el.get("type")}"}} to {tid}.boundElements'
                )

        for bound in el.get("boundElements") or []:
            bid = bound.get("id") if isinstance(bound, dict) else None
            if bid not in by_id:
                errors.append(f"{eid}: boundElements references missing element '{bid}'")
            elif not points_back(by_id[bid], eid):
                errors.append(f"{eid}: boundElements lists '{bid}', but '{bid}' is not bound to {eid}. Remove the entry")

    return errors


def compute_bounding_box(elements: list[dict]) -> tuple[float, float, float, float]:
    """Compute bounding box (min_x, min_y, max_x, max_y) across all elements."""
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for el in elements:
        if el.get("isDeleted"):
            continue
        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("width", 0)
        h = el.get("height", 0)

        # For arrows/lines, points array defines the shape relative to x,y
        if el.get("type") in ("arrow", "line") and "points" in el:
            for px, py in el["points"]:
                min_x = min(min_x, x + px)
                min_y = min(min_y, y + py)
                max_x = max(max_x, x + px)
                max_y = max(max_y, y + py)
        else:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + abs(w))
            max_y = max(max_y, y + abs(h))

    if min_x == float("inf"):
        return (0, 0, 800, 600)

    return (min_x, min_y, max_x, max_y)


def render(
    excalidraw_path: Path,
    output_path: Path | None = None,
    scale: int = 2,
    max_width: int = 1920,
) -> Path:
    """Render an .excalidraw file to PNG. Returns the output PNG path."""
    # Import playwright here so validation errors show before import errors
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run the script with: uv run render_excalidraw.py ...", file=sys.stderr)
        sys.exit(1)

    # Read and validate
    raw = excalidraw_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {excalidraw_path}: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_excalidraw(data)
    if errors:
        print("ERROR: Invalid Excalidraw file:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Compute viewport size from element bounding box, plus the stage padding in the template
    elements = [e for e in data["elements"] if not e.get("isDeleted")]
    min_x, min_y, max_x, max_y = compute_bounding_box(elements)
    padding = 160
    diagram_w = max_x - min_x + padding
    diagram_h = max_y - min_y + padding

    vp_width = min(int(diagram_w), max_width)
    vp_height = max(int(diagram_h), 600)

    if output_path is None:
        output_path = excalidraw_path.with_suffix(".png")

    # Template path (same directory as this script)
    template_path = Path(__file__).parent / "render_template.html"
    if not template_path.exists():
        print(f"ERROR: Template not found at {template_path}", file=sys.stderr)
        sys.exit(1)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "browserType.launch" in str(e):
                print("ERROR: Chromium not installed. Run: uv run render_excalidraw.py --install", file=sys.stderr)
                sys.exit(1)
            raise

        page = browser.new_page(
            viewport={"width": vp_width, "height": vp_height},
            device_scale_factor=scale,
        )

        page.goto(template_path.as_uri())

        # Wait for the ES module to load (imports from the CDN)
        page.wait_for_function("window.__moduleReady === true", timeout=60000)

        result = page.evaluate("data => window.renderDiagram(data)", data)

        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown render error") if result else "renderDiagram returned null"
            print(f"ERROR: Render failed: {error_msg}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        page.wait_for_function("window.__renderComplete === true", timeout=15000)

        # Screenshot the stage, which carries the background and padding
        stage = page.query_selector("#stage")
        if stage is None:
            print("ERROR: No stage element found after render.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        stage.screenshot(path=str(output_path))
        browser.close()

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Excalidraw JSON to PNG")
    parser.add_argument("input", type=Path, nargs="?", help="Path to .excalidraw JSON file")
    parser.add_argument("--install", action="store_true", help="Install the headless browser, then exit")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output PNG path (default: same name with .png)")
    parser.add_argument("--scale", "-s", type=int, default=2, help="Device scale factor (default: 2)")
    parser.add_argument("--width", "-w", type=int, default=1920, help="Max viewport width (default: 1920)")
    args = parser.parse_args()

    if args.install:
        sys.exit(subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"]))

    if args.input is None:
        parser.error("input is required (or pass --install)")

    if not args.input.exists():
        print(f"ERROR: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    png_path = render(args.input, args.output, args.scale, args.width)
    print(str(png_path))


if __name__ == "__main__":
    main()
