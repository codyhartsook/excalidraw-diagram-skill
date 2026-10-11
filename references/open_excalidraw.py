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
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagram import code_refs, find_symbol, load_local, load_repos, resolve, write_scene  # noqa: E402
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


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def diff_base(root: Path, repo: dict, ref: dict) -> str | None:
    """Where the checkout's branch split off the repo's branch, if the working file changed since."""
    fork = git(root, "merge-base", f"origin/{repo.get('branch', 'main')}", "HEAD")
    if fork.returncode or git(root, "diff", "--quiet", fork.stdout.strip(), "--", ref["path"]).returncode != 1:
        return None
    return fork.stdout.strip()


def resolved_refs(path: Path) -> dict:
    """element id -> (ref, local checkout, repo config) for every code ref in the diagram."""
    data = json.loads(path.read_text(encoding="utf-8"))
    repos, local = load_repos(path), load_local()
    return {el["id"]: (ref, local.get(ref["repo"]), repos.get(ref["repo"])) for el, ref in code_refs(data)}


def code_links(path: Path) -> dict:
    """Where Cmd+click goes (VS Code when checked out, else GitHub), and whether Shift+Cmd+click has a diff."""
    repos, local, links = load_repos(path), load_local(), {}
    for el_id, (ref, root, repo) in resolved_refs(path).items():
        github, vscode, _, _ = resolve(ref, repos, local)
        if vscode or github:
            symbol = f"#{ref['symbol']}" if ref.get("symbol") else ""
            links[el_id] = {"url": vscode or github, "ref": f"{ref['path']}{symbol}",
                            "target": "VS Code" if vscode else "GitHub",
                            "diff": bool(root and repo and diff_base(root, repo, ref))}
    return links


def in_repo_window(root: Path, *args: str) -> None:
    """Run a VS Code command in the window that has the repo open, so the language tooling sees its module.
    "code <root>" focuses that window, or opens one; --reuse-window then targets it."""
    subprocess.run(["code", str(root)], capture_output=True, timeout=20)
    subprocess.Popen(["code", "--reuse-window", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_code(path: Path, element_id: str, diff: bool) -> str | None:
    """Open the element's code in VS Code: the file at its symbol, or with diff=True, VS Code's diff of the
    file from the branch point (left) to the working copy (right). Returns an error message, or None."""
    if not shutil.which("code"):
        return "the VS Code 'code' command is not on PATH"
    ref, root, repo = resolved_refs(path).get(element_id, (None, None, None))
    if not ref or not root or not (root / ref["path"]).is_file():
        return "no local checkout of this code"
    file = (root / ref["path"]).resolve()
    if not diff:
        line = find_symbol(file.read_text(encoding="utf-8", errors="replace"), ref["symbol"]) if ref.get("symbol") else None
        in_repo_window(root, "--goto", f"{file}:{line or 1}")
        return None
    fork = diff_base(root, repo, ref) if ref and root and repo else None
    if not fork:
        return "no changes to show"
    # Left side: the file at the branch point, saved where its path still reads well in the tab title.
    snapshot = Path(tempfile.gettempdir()) / "excalidraw-diff" / ref["repo"] / f"{repo.get('branch', 'main')}@{fork[:8]}" / ref["path"]
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shown = git(root, "show", f"{fork}:{ref['path']}")
    snapshot.write_text(shown.stdout if shown.returncode == 0 else "", encoding="utf-8")  # empty when the branch added it
    in_repo_window(root, "--diff", str(snapshot), str(file))
    return None


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
            elif self.path == "/links.json":
                self._send(HTTPStatus.OK, json.dumps(code_links(path)).encode(), "application/json")
            else:
                self._send(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path not in ("/save", "/open-code"):
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
            if self.path == "/open-code":
                error = open_code(path, str(saved.get("id", "")), bool(saved.get("diff")))
                self._send(HTTPStatus.CONFLICT if error else HTTPStatus.NO_CONTENT, (error or "").encode())
                return
            if saved.get("type") != "excalidraw" or not isinstance(saved.get("elements"), list):
                self._send(HTTPStatus.BAD_REQUEST, b"not an Excalidraw scene")
                return
            # The editor drops appState keys it does not know, so carry the original ones over
            # rather than silently lose them.
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
