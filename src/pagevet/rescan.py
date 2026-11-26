"""Re-scan pages and report what changed since the last scan: the core of scheduled change alerts.

    from pagevet.rescan import rescan
    out = rescan(["https://example.com/"], previous=last_report)
    if out["alert"]:
        notify(out["new"])
    last_report = out["report"]

``rescan`` returns the full new report (keep it for next time) and only the findings that are not
in ``previous``, matched as ``--baseline`` matches them. A scheduler (Windmill, cron, a CI
schedule) stores the report between runs; ``integrations/windmill/pagevet_rescan.py`` is one.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from pagevet.scan import SEVERITIES, fingerprint, main

Fetcher = Callable[[str], str]


def rescan(sources: list[str], previous: list[dict] | None = None, alert_on: str = "medium",
           fetch_css: bool = False, ignore_robots: bool = False, max_pages: int = 50,
           fetcher: Fetcher | None = None, robots_fetcher: Fetcher | None = None,
           css_fetcher: Fetcher | None = None) -> dict:
    """Scan ``sources``; return the report, the findings new since ``previous``, counts and ``alert``.

    ``alert`` is true when a new finding is at or above ``alert_on`` (low, medium or high).
    "gone" counts findings of ``previous`` on pages scanned again without an error that no
    longer appear. The ``*_fetcher`` arguments replace network access, for tests.
    """
    if alert_on not in SEVERITIES:
        raise ValueError(f"alert_on must be one of {', '.join(SEVERITIES)}")
    if not sources:
        raise ValueError("give at least one source")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.json"
        argv = [*sources, "--format", "json", "--out", str(out), "--max-pages", str(max_pages), "--delay", "0"]
        argv += ["--fetch-css"] * fetch_css + ["--ignore-robots"] * ignore_robots
        main(argv, fetcher=fetcher, robots_fetcher=robots_fetcher, css_fetcher=css_fetcher, sleep=lambda s: None)
        report = json.loads(out.read_text(encoding="utf-8"))

    def key(page: dict, f: dict) -> str:
        return fingerprint(page["source"], f["channel"], f["kinds"], f["excerpt"])

    known = {key(p, f): p["source"] for p in previous or [] for f in p.get("findings", [])}
    seen, new = set(), []
    for page in report:
        for f in page["findings"]:
            k = key(page, f)
            seen.add(k)
            if k not in known:
                new.append({"source": page["source"], **{n: f[n] for n in ("channel", "kinds", "severity", "excerpt", "advice")}})
    rescanned = {p["source"] for p in report if not p["error"]}
    gone = sum(1 for k, src in known.items() if src in rescanned and k not in seen)
    floor = SEVERITIES.index(alert_on)
    return {
        "report": report,
        "new": new,
        "counts": {"pages": len(report), "errors": sum(1 for p in report if p["error"]),
                   "new": len(new), "unchanged": len(seen & set(known)), "gone": gone},
        "alert": any(SEVERITIES.index(f["severity"]) >= floor for f in new),
    }
