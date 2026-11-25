"""Fetch a clean-page list once and record what PageVet reports, keeping hashes, not page copies.

    uv run python docs/bench/clean_pages.py docs/bench/2026-11-19-clean-pages/urls.txt results.jsonl

One request per host for the page, plus robots.txt; a page robots.txt disallows for a generic
crawler is skipped. Pages are fetched over plain HTTP with PageVet's own fetcher, then scanned.
Each output line has the URL, outcome, SHA-256 and size of the body, and the findings (channel,
kinds, severity, excerpt). Re-running later will differ where the sites have changed; the
hashes record what was scanned.
"""
import concurrent.futures as cf
import hashlib
import json
import sys
import urllib.robotparser
from urllib.parse import urlsplit

from pagevet.scan import fetch, scan_text

UA = "pagevet (page audit for text aimed at AI models)"


def one(url: str) -> dict:
    parts = urlsplit(url)
    rec = {"url": url, "host": parts.netloc}
    try:
        robots = urllib.robotparser.RobotFileParser()
        try:
            robots.parse(fetch(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout=10, max_bytes=500_000, user_agent=UA).splitlines())
            if not robots.can_fetch(UA, url):
                return {**rec, "outcome": "robots_disallowed"}
        except Exception:  # noqa: S110 - no readable robots.txt means allowed
            pass
        body = fetch(url, timeout=20, max_bytes=5_000_000, user_agent=UA)
        raw = body.encode("utf-8", "replace")
        result = scan_text(url, body)
        return {**rec, "outcome": "scanned", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "findings": [{"channel": f.channel, "kinds": f.kinds, "severity": f.severity, "excerpt": f.excerpt} for f in result.findings]}
    except Exception as exc:
        return {**rec, "outcome": "error", "error": f"{type(exc).__name__}: {exc}"[:200]}


urls = [line.strip() for line in open(sys.argv[1]) if line.strip().startswith("http")]
with cf.ThreadPoolExecutor(max_workers=16) as pool:
    rows = list(pool.map(one, urls))
with open(sys.argv[2], "w") as out:
    for row in rows:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
counts: dict[str, int] = {}
for row in rows:
    counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
sys.stdout.write(json.dumps(counts) + "\n")
