"""Scan pages through a crawlee-server instance (page mode, capture on) and record the results.

    PAGEVET_CRAWL_URL=... PAGEVET_CRAWL_TOKEN=... \\
      uv run python docs/bench/scripts/crawlee_run.py urls.txt results.jsonl [--only-unread earlier.jsonl]

URLs go to crawlee-server ten at a time (its limit per request) in ``mode: page``, so only the
listed pages are fetched. Each stored capture is read back and scanned with PageVet's default
rules. With ``--only-unread``, URLs that an earlier plain-HTTP run (clean_pages.py output) already
scanned are skipped, so the run covers what plain HTTP could not read.
"""
import argparse
import concurrent.futures as cf
import json
import sys
from urllib.parse import urlsplit

from pagevet.scan import scan_text
from pagevet.sources import crawl

ap = argparse.ArgumentParser()
ap.add_argument("urls")
ap.add_argument("out")
ap.add_argument("--only-unread", metavar="EARLIER_JSONL")
ap.add_argument("--workers", type=int, default=3)
args = ap.parse_args()

urls = [line.strip() for line in open(args.urls) if line.strip().startswith("http")]
if args.only_unread:
    done = {json.loads(line)["url"] for line in open(args.only_unread) if json.loads(line)["outcome"] == "scanned"}
    urls = [u for u in urls if u not in done]
batches = [urls[i:i + 10] for i in range(0, len(urls), 10)]


def host(url: str) -> str:
    return urlsplit(url).hostname or ""


def run(batch: list[str]) -> list[dict]:
    report: dict = {}
    try:
        pages, _ = crawl(batch, max_pages=len(batch), mode="page", report=report)
    except Exception as exc:
        if len(batch) > 1:  # one bad URL fails the whole request: retry one at a time
            return [row for u in batch for row in run([u])]
        return [{"url": batch[0], "outcome": "error", "error": f"{type(exc).__name__}: {exc}"[:200]}]
    reasons = {host(f.get("url", "")): f.get("error", "") for f in report.get("failures", [])}
    reasons |= {host(f.get("url", "")): f.get("reason", "refused") for f in report.get("refused", []) if isinstance(f, dict)}
    by_host = {host(p.url): p for p in pages}
    rows = []
    for u in batch:
        page = by_host.get(host(u))
        if page is None:
            rows.append({"url": u, "outcome": "not_read", "reason": reasons.get(host(u), "no record")})
            continue
        result = scan_text(page.url, page.body)
        rows.append({"url": u, "final_url": page.url, "outcome": "scanned", **page.evidence,
                     "findings": [{"channel": f.channel, "kinds": f.kinds, "severity": f.severity, "excerpt": f.excerpt} for f in result.findings]})
    return rows


with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
    rows = [row for chunk in pool.map(run, batches) for row in chunk]
with open(args.out, "w") as out:
    for row in rows:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
counts: dict[str, int] = {}
for row in rows:
    counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
sys.stdout.write(json.dumps({"urls": len(urls), **counts}) + "\n")
