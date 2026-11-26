"""pagevet-bench: measure the detector on labelled text.

    pagevet-bench cases.jsonl --out results.json

Each line of the input is ``{"id": ..., "text": ..., "label": 1 or 0, "group": ...}``; label 1
means the text contains an injected instruction. The report gives the catch rate on label-1 cases
and the false-alarm rate on label-0 cases, each with a 95% Wilson interval, plus the catch rate
per group. By default it runs the patterns only: no model, no network. ``--detector`` selects
an optional layer (see ``pagevet.detectors``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from pagevet import __version__
from pagevet.detectors import Detector, PatternDetector, build


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for ``hits`` out of ``n`` (0, 0 when n is 0)."""
    if n == 0:
        return 0.0, 0.0
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def _rate(hits: int, n: int) -> dict:
    lo, hi = wilson(hits, n)
    return {"hits": hits, "n": n, "rate": round(hits / n, 4) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}


def run(cases: list[dict], detector: Detector | None = None, batch: int = 64) -> dict:
    """Score ``detector`` (the patterns by default) on ``cases``; return the report as a dict."""
    detector = detector or PatternDetector()
    verdicts = []
    for i in range(0, len(cases), batch):
        verdicts += detector.judge([c["text"] for c in cases[i:i + batch]])
    pos = neg = caught = alarms = 0
    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    kinds: Counter = Counter()
    false_alarm_ids, missed = [], []
    for case, verdict in zip(cases, verdicts, strict=True):
        flagged = verdict.flagged
        if case["label"]:
            pos += 1
            caught += flagged
            g = groups[str(case.get("group", ""))]
            g[0] += flagged
            g[1] += 1
            if flagged:
                kinds.update({k.split(":")[0] for k in verdict.detail.split(", ") if k})
            elif len(missed) < 20:
                missed.append(case["id"])
        else:
            neg += 1
            alarms += flagged
            if flagged and len(false_alarm_ids) < 20:
                false_alarm_ids.append(case["id"])
    return {
        "tool": "pagevet", "version": __version__, "detector": detector.name,
        "catch_rate": _rate(caught, pos),
        "false_alarm_rate": _rate(alarms, neg),
        "by_group": {g: _rate(h, n) for g, (h, n) in sorted(groups.items())},
        "kinds_on_caught": dict(kinds.most_common()),
        "sample_missed_ids": missed,
        "sample_false_alarm_ids": false_alarm_ids,
    }


def render(report: dict) -> str:
    """Render the report as a short text table."""
    c, f = report["catch_rate"], report["false_alarm_rate"]
    pct = lambda r: "n/a" if r["rate"] is None else f"{r['rate']:.1%} ({r['hits']}/{r['n']}, 95% CI {r['ci95'][0]:.1%}-{r['ci95'][1]:.1%})"  # noqa: E731
    lines = [f"catch rate        {pct(c)}", f"false-alarm rate  {pct(f)}", "", "by group:"]
    lines += [f"  {g or '(none)':32} {pct(r)}" for g, r in report["by_group"].items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, langfuse_client: object | None = None) -> int:
    """Run the command line; return the exit code."""
    parser = argparse.ArgumentParser(prog="pagevet-bench", description="Measure pagevet's detector on labelled text (JSONL).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("cases", help="JSONL file: id, text, label (1 = contains an injection, 0 = clean), group")
    parser.add_argument("--out", metavar="FILE", help="also write the full report as JSON")
    parser.add_argument("--detector", default="patterns", metavar="NAME",
                        help="patterns (default), promptguard, jev, llm, or several joined with + (flag when any does)")
    parser.add_argument("--limit", type=int, default=0, help="only the first N cases (a cheaper trial of a billed detector)")
    parser.add_argument("--dry-run", action="store_true", help="say how many cases (and billed calls) a run would make, and stop")
    parser.add_argument("--langfuse", action="store_true", help='also record the run in Langfuse (LANGFUSE_* keys, pip install "pagevet[langfuse]")')
    args = parser.parse_args(argv)
    from pagevet.config import load_env_file

    load_env_file()
    try:
        detector = build(args.detector)
    except ValueError as exc:
        parser.error(str(exc))
    raw = Path(args.cases).read_bytes()
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]
    billed = sum(n in ("jev", "llm") for n in args.detector.split("+"))
    if args.dry_run:
        sys.stdout.write(f"{len(cases)} cases; {len(cases) * billed} billed calls ({args.detector}). Nothing was sent.\n")
        return 0
    report = run(cases, detector)
    report["cases_sha256"] = hashlib.sha256(raw).hexdigest()
    sys.stdout.write(render(report))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.langfuse:
        try:
            from pagevet.tracing import record_bench

            sys.stderr.write(f"pagevet-bench: recorded in Langfuse, trace {record_bench(report, args.cases, langfuse_client)}\n")
        except Exception as exc:  # noqa: BLE001  recording never changes the result
            sys.stderr.write(f"pagevet-bench: Langfuse recording skipped: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
