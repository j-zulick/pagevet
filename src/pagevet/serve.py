"""A small local HTTP API for PageVet, for n8n, Windmill and other tools that call a URL.

    pagevet-serve                       # http://127.0.0.1:8790
    pagevet-serve --port 9000

    POST /scan   {"url": "https://…"}  or  {"html": "…", "source": "name"}   -> PageVet's JSON report for that page
    POST /guard  same body, plus optional "policy": "high" | "medium" | "never" -> {allowed, text, findings, removed}
    GET  /health                                                             -> {"ok": true, "pagevet": "<version>"}

Binds to 127.0.0.1 unless ``--host`` says otherwise. URLs are fetched with non-public addresses refused on every
redirect, as in the MCP server. Bodies over 5 MB are refused. Standard library only; one request at a time.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer

from pagevet import __version__
from pagevet.guard import POLICIES, guard
from pagevet.scan import fetch, scan_text

MAX_BODY = 5_000_000


def handle(path: str, payload: dict, fetcher: Callable[[str], str]) -> tuple[int, dict]:
    """Answer one API call: (HTTP status, JSON body). Separate from the server so it is testable."""
    if path not in ("/scan", "/guard"):
        return 404, {"error": "unknown path; use POST /scan or /guard"}
    url, page = payload.get("url"), payload.get("html")
    if bool(url) == bool(page is not None):
        return 400, {"error": "give exactly one of url or html"}
    source = url or str(payload.get("source") or "html")
    try:
        body = fetcher(url) if url else str(page)
    except Exception as exc:  # the page, not the server, failed
        return 502, {"error": f"{type(exc).__name__}: {exc}"[:300], "source": source}
    if path == "/scan":
        return 200, asdict(scan_text(source, body))
    policy = payload.get("policy", "high")
    if policy not in POLICIES:
        return 400, {"error": f"policy must be one of {', '.join(POLICIES)}"}
    return 200, asdict(guard(source, body, policy))


def make_handler(fetcher: Callable[[str], str]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"pagevet/{__version__}"

        def _send(self, status: int, data: dict) -> None:
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            self._send(200, {"ok": True, "pagevet": __version__}) if self.path == "/health" else self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": "body too large"})
            try:
                payload = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("not an object")
            except ValueError:
                return self._send(400, {"error": "body must be a JSON object"})
            self._send(*handle(self.path, payload, fetcher))

        def log_message(self, fmt: str, *args: object) -> None:
            sys.stderr.write(f"pagevet-serve: {fmt % args}\n")

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagevet-serve", description="Run PageVet as a local HTTP API.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)
    server = HTTPServer((args.host, args.port), make_handler(lambda u: fetch(u, allow_private=False, max_bytes=MAX_BODY)))
    sys.stderr.write(f"pagevet-serve: http://{args.host}:{args.port} (POST /scan, /guard; GET /health)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
