# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Open an .excalidraw file in an editable Excalidraw canvas in the browser.

Usage:
    uv run open_excalidraw.py <path-to-file.excalidraw> [--port 0] [--no-browser]

The script serves the diagram from 127.0.0.1 and opens it in the default browser. The
page loads the Excalidraw editor from esm.sh, but the diagram itself stays on this machine.

"Save to file" (or Cmd/Ctrl+S) writes the edited scene back to the same file. The server
runs until you stop it with Ctrl+C, so an agent should start it in the background.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagram import write_scene  # noqa: E402
from render_excalidraw import validate_excalidraw  # noqa: E402  (no Playwright needed)

TEMPLATE = Path(__file__).resolve().parent / "editor_template.html"


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: Invalid JSON in {path}: {e}")
    errors = validate_excalidraw(data)
    if errors:
        print("ERROR: Invalid Excalidraw file:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    return data


def make_handler(path: Path):
    page = TEMPLATE.read_text(encoding="utf-8").replace("__TITLE__", path.stem)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes = b"", ctype: str = "text/plain") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, page.encode(), "text/html; charset=utf-8")
            elif self.path == "/scene.json":
                self._send(HTTPStatus.OK, path.read_bytes(), "application/json")
            else:
                self._send(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path != "/save":
                self._send(HTTPStatus.NOT_FOUND)
                return
            # A cross-site page can only send JSON after a CORS preflight, which this server never answers.
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, b"expected application/json")
                return
            try:
                saved = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except (ValueError, json.JSONDecodeError):
                self._send(HTTPStatus.BAD_REQUEST, b"invalid JSON")
                return
            if saved.get("type") != "excalidraw" or not isinstance(saved.get("elements"), list):
                self._send(HTTPStatus.BAD_REQUEST, b"not an Excalidraw scene")
                return
            # The editor drops appState keys it does not know, such as ambientGlow for the
            # renderer, so carry the original ones over rather than silently lose them.
            original = json.loads(path.read_text(encoding="utf-8")).get("appState", {})
            saved["appState"] = {**original, **saved.get("appState", {})}
            write_scene(path, saved)
            print(f"saved {path}", flush=True)
            self._send(HTTPStatus.NO_CONTENT)

        def log_message(self, *args) -> None:  # keep the terminal quiet apart from saves
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Open an .excalidraw file in an editable browser canvas")
    parser.add_argument("input", type=Path, help="Path to the .excalidraw file")
    parser.add_argument("--port", type=int, default=0, help="Local port (default: any free port)")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening a browser")
    args = parser.parse_args()

    path = args.input.resolve()
    if not path.exists():
        sys.exit(f"ERROR: {path} does not exist")
    load(path)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(path))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Editing {path}\n  {url}\n  Save to file (or Cmd/Ctrl+S) writes back. Ctrl+C stops the server.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
