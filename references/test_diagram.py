# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Self-check for diagram.py and the binding validator. Run: uv run --script test_diagram.py"""

import copy
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from diagram import expand, summarize, write_scene  # noqa: E402
from render_excalidraw import validate_excalidraw  # noqa: E402


def scene(*elements):
    return {"type": "excalidraw", "version": 2, "elements": [copy.deepcopy(e) for e in elements],
            "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}


BOX_A = {"type": "rectangle", "id": "a", "x": 0, "y": 0, "width": 100, "height": 50, "label": "A"}
BOX_B = {"type": "rectangle", "id": "b", "x": 300, "y": 0, "width": 100, "height": 50}
ARROW = {"type": "arrow", "id": "ab", "from": "a", "to": "b", "label": "call"}


def test_one_sided_binding_is_caught_then_repaired():
    data = scene(BOX_A, BOX_B, ARROW)
    assert expand(data) == []
    by_id = {e["id"]: e for e in data["elements"]}
    by_id["a"]["boundElements"] = []  # what a careless hand edit leaves behind
    assert any("does not list it" in err for err in validate_excalidraw(data))
    assert expand(data) == [] and validate_excalidraw(data) == []


def test_expand_is_idempotent_on_disk():
    data = scene(BOX_A, BOX_B, ARROW)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "d.excalidraw"
        expand(data)
        write_scene(path, data)
        first = path.read_text()
        again = json.loads(first)
        assert expand(again) == []
        write_scene(path, again)
        assert path.read_text() == first
        assert len(first.splitlines()) == len(data["elements"]) + 8  # wrapper lines plus one per element


def test_given_fields_win_and_arrow_meets_outlines():
    data = scene({**BOX_A, "strokeColor": "#e03131", "roughness": 0}, BOX_B, ARROW)
    expand(data)
    by_id = {e["id"]: e for e in data["elements"]}
    assert by_id["a"]["strokeColor"] == "#e03131" and by_id["a"]["roughness"] == 0
    assert by_id["b"]["roughness"] == 1 and by_id["a_label"]["fontFamily"] == 5
    arrow = by_id["ab"]
    assert (arrow["x"], arrow["y"]) == (104, 25)  # right edge of a, plus the gap
    assert arrow["x"] + arrow["points"][-1][0] == 296  # left edge of b, minus the gap


def test_label_follows_a_moved_container():
    data = scene(BOX_A)
    expand(data)
    data["elements"][0]["x"] += 200
    expand(data)
    box, label = data["elements"]
    assert abs((label["x"] + label["width"] / 2) - (box["x"] + box["width"] / 2)) < 0.01


def test_summary_folds_labels_and_skips_volatile_fields():
    data = scene(BOX_A, BOX_B, ARROW)
    expand(data)
    before = summarize(data)
    data["elements"][0]["version"] = 99
    assert summarize(data) == before
    assert 'a rectangle 0,0 100x50 "A"' in before and "ab arrow a -> b" in before and "a_label" not in before


def test_templates_expand_cleanly():
    md = (HERE / "element-templates.md").read_text()
    elements = [json.loads(line) for block in re.findall(r"```json\n(.*?)```", md, re.S) for line in block.splitlines()]
    ids = {e["id"] for e in elements}
    stubs = [{"type": "rectangle", "id": i, "x": 0, "y": 900 + n * 100, "width": 80, "height": 40}
             for n, i in enumerate(sorted({e.get(k) for e in elements for k in ("from", "to")} - ids - {None}))]
    data = scene(*elements, *stubs)
    assert expand(data) == []


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
