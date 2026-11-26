"""Patterns against an open-weights classifier, on the same cases and the same saved real pages.

    uv run python docs/bench/scripts/head_to_head.py pages PAGES.jsonl.gz DETECTOR OUT.json [--max-windows N]

``pages`` runs a detector (``patterns``, ``protectai``, ``patterns+protectai``…) on the text a model reads
from each saved page (every channel PageVet separates, joined) and counts pages flagged: a false-alarm rate,
since these lists are ordinary pages. A classifier reads at most ``--max-windows`` 512-token windows per page
(default 8, about the first 4,000 tokens), which is stated with the results. Labelled cases (BIPIA,
deepset, evasion) go through ``pagevet-bench --detector`` instead.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

from pagevet import __version__
from pagevet.detectors import build
from pagevet.scan import looks_like_html, split_html


def page_text(page_html: str, max_chars: int) -> str:
    if not looks_like_html(page_html):
        return page_html[:max_chars]
    ch = split_html(page_html)
    parts = [*ch.visible, *ch.user_content, *ch.hidden, *ch.hidden_by_css, *ch.comments, *ch.attributes, *ch.structured, *ch.noscript]
    return "\n".join(parts)[:max_chars]


def main() -> int:
    mode, pages, spec, out = sys.argv[1:5]
    if mode != "pages":
        raise SystemExit("usage: head_to_head.py pages PAGES DETECTOR OUT [--max-windows N]")
    max_windows = int(sys.argv[sys.argv.index("--max-windows") + 1]) if "--max-windows" in sys.argv else 8
    detector = build(spec)
    rows, t0 = [], time.perf_counter()
    with gzip.open(pages, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            if "html" not in r:
                continue
            text = page_text(r["html"], max_windows * 2000)  # about 4 characters per token, 512-token windows
            v = detector.judge([text])[0]
            rows.append({"set": r["lang"], "url": r["url"], "flagged": v.flagged, "score": v.score})
    flagged = sum(r["flagged"] for r in rows)
    summary = {"detector": spec, "pagevet": __version__, "pages": len(rows), "flagged": flagged,
               "max_windows": max_windows, "seconds": round(time.perf_counter() - t0, 1)}
    Path(out).write_text(json.dumps({"summary": summary, "pages": rows}, indent=1, ensure_ascii=False) + "\n")
    sys.stdout.write(json.dumps(summary) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
