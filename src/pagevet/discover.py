"""Find the pages that search results (and the AI answers built on them) draw on for a topic.

    pagevet-discover "best front brake rotors" "brake rotors sale" --per-query 10 --out urls.txt
    pagevet --urls urls.txt --format html --out report.html

Each query goes to a SearXNG instance (``PAGEVET_SEARXNG_URL``, JSON format enabled), and the
result URLs are written one per line, de-duplicated, with ``#`` comment lines recording which
query found them, so the list can be scanned with ``pagevet --urls`` and the study repeated.
Use ``--from-json`` instead to read results you collected with another search tool.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

from pagevet import __version__

Get = Callable[[str, dict], dict]  # (url, params) -> parsed JSON


def _get(url: str, params: dict, timeout: float = 30.0) -> dict:
    import httpx

    headers = {"User-Agent": "pagevet (page audit for text aimed at AI models)"}
    token = os.environ.get("PAGEVET_SEARXNG_TOKEN", "").strip()
    if token:
        headers["authorization"] = f"Bearer {token}"
    resp = httpx.get(url, params=params, headers=headers, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def searxng_search(query: str, per_query: int = 10, get: Get = _get, base: str | None = None) -> list[str]:
    """Return up to ``per_query`` http(s) result URLs for ``query`` from SearXNG."""
    base = (base or os.environ.get("PAGEVET_SEARXNG_URL", "")).strip().rstrip("/")
    if not base:
        raise RuntimeError("PAGEVET_SEARXNG_URL is not set (a SearXNG instance with the JSON format enabled)")
    data = get(f"{base}/search", {"q": query, "format": "json"})
    urls = []
    for r in data.get("results") or []:
        url = r.get("url", "")
        if url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
        if len(urls) >= per_query:
            break
    return urls


def write_list(found: dict[str, list[str]], path: str | None, max_per_host: int = 0) -> list[str]:
    """Write the URLs, grouped by the first query that found them; return the URLs written.

    ``max_per_host`` (0 = no limit) keeps any one site from dominating the sample.
    """
    seen: set[str] = set()
    per_host: dict[str, int] = {}
    lines, kept = [], []
    for query, urls in found.items():
        lines.append(f"# query: {query}")
        for url in urls:
            host = urlsplit(url).hostname or ""
            if url in seen or (max_per_host and per_host.get(host, 0) >= max_per_host):
                continue
            seen.add(url)
            per_host[host] = per_host.get(host, 0) + 1
            lines.append(url)
            kept.append(url)
    text = "\n".join(lines) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return kept


def main(argv: list[str] | None = None, get: Get = _get) -> int:
    """Run the command line; return the exit code."""
    from pagevet.config import load_env_file

    parser = argparse.ArgumentParser(prog="pagevet-discover", description="Collect the pages search results draw on for a topic.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("queries", nargs="*", help="search queries")
    parser.add_argument("--per-query", type=int, default=10, metavar="N", help="results to keep per query (default 10)")
    parser.add_argument("--max-per-host", type=int, default=0, metavar="N", help="at most N URLs from one site (default: no limit)")
    parser.add_argument("--from-json", metavar="FILE",
                        help='read {"query": ["url", ...]} collected with another search tool instead of querying SearXNG')
    parser.add_argument("--out", metavar="FILE", help="write the URL list to FILE (default: stdout)")
    args = parser.parse_args(argv)
    load_env_file()
    if args.from_json:
        found = {q: [u for u in urls if str(u).startswith(("http://", "https://"))]
                 for q, urls in json.loads(Path(args.from_json).read_text(encoding="utf-8")).items()}
    else:
        if not args.queries:
            parser.error("give at least one query, or --from-json")
        found = {}
        for q in args.queries:
            try:
                found[q] = searxng_search(q, args.per_query, get)
            except Exception as exc:  # report and keep going
                sys.stderr.write(f"pagevet-discover: {q!r}: {type(exc).__name__}: {exc}\n")
                found[q] = []
    kept = write_list(found, args.out, args.max_per_host)
    sys.stderr.write(f"pagevet-discover: {len(kept)} URL(s) from {len(found)} quer{'y' if len(found) == 1 else 'ies'}\n")
    return 0 if kept else 2
