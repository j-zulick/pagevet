"""Scores from PageVet's own reports (0.4.0): page risk, site AI visibility, and an opportunity score.

    python -m pagevet.scores --scan scan.json --access access.json --traffic traffic.json --out scores.json
    python -m pagevet.scores --access access.json --format csv

Inputs are the JSON reports PageVet already writes: ``pagevet --format json`` (``--scan``), ``pagevet-access
--format json`` (``--access``) and ``python -m pagevet.traffic`` (``--traffic``). Any of them may be left out; a score
part that needs a missing input is reported as not measured, never guessed.

- **Page risk (0-100, higher is worse):** from the findings on each page: severity, a hidden channel, commercial
  intent, memory planting, and text served differently to AI crawlers.
- **Site AI visibility (0-100, higher is more visible):** the share of AI search and AI fetch crawlers allowed,
  no firewall refusals, ``llms.txt``, and, with a traffic report, whether AI crawlers and search engines were seen.
  Training crawlers are listed but not scored: refusing them is a business choice, not a defect.
- **Opportunity (0-100):** the visibility gap and the worst page risk combined, for ranking which sites to look at
  first.

Every score carries the reasons behind it. Weights live in ``src/pagevet/data/scoring.json`` with a ``score_version``;
scores from different versions are not comparable. These are ranking aids from deterministic rules, not detection
rates, and nothing here is tuned on the published benchmark sets.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

from pagevet import __version__

VISIBLE_CHANNELS = {"visible text", "user-submitted content", "AI share links"}
SERVED_DIFFERENTLY = {"content_differs", "fetch_differs", "cloaked_instruction"}


def load_weights(path: str | None = None) -> dict:
    text = Path(path).read_text(encoding="utf-8") if path else resources.files("pagevet").joinpath("data/scoring.json").read_text(encoding="utf-8")
    w = json.loads(text)
    for key in ("score_version", "risk", "visibility", "opportunity", "gaps"):
        if key not in w:
            raise ValueError(f"scoring weights: missing {key!r}")
    return w


def _host(url: str) -> str:
    p = urlsplit(url if "://" in url else f"file://{url}")
    return p.netloc.lower() or "(local)"


# --- page risk ------------------------------------------------------------------------------------

def page_risk(result: dict, weights: dict) -> dict:
    """Risk score for one result of ``pagevet --format json``."""
    w = weights["risk"]
    score, reasons = 0, []
    for f in result.get("findings", []):
        sev = f.get("severity", "low")
        pts = w["severity"].get(sev, 0)
        why = [f"{sev} finding in {f.get('channel', '?')}"]
        if f.get("channel") not in VISIBLE_CHANNELS:
            pts += w["hidden_channel"]
            why.append("hidden from readers")
        if f.get("intent") == "commercial":
            pts += w["commercial_intent"]
            why.append("commercial intent")
        kinds = set(f.get("kinds", []))
        if "memory_planting" in kinds:
            pts += w["memory_planting"]
            why.append("memory planting")
        if kinds & SERVED_DIFFERENTLY:
            pts += w["served_differently"]
            why.append("served differently to AI crawlers")
        score += pts
        reasons.append({"points": pts, "why": ", ".join(why), "excerpt": (f.get("excerpt") or "")[:120]})
    return {"url": result.get("source", ""), "score": min(score, w["cap"]), "findings": len(result.get("findings", [])),
            "reasons": reasons, "read": not result.get("error")}


# --- site visibility ------------------------------------------------------------------------------

def _allowed(rows: list[dict]) -> tuple[int, int]:
    return sum(not r["verdict"].startswith("refused") for r in rows), len(rows)


def site_visibility(access: dict | None, traffic: dict | None, weights: dict) -> dict:
    """Visibility score for one ``pagevet-access`` report (dict) plus an optional traffic report."""
    w = weights["visibility"]
    parts, measured_max = [], 0

    def part(name: str, points: float, max_points: int, detail: str) -> None:
        nonlocal measured_max
        measured_max += max_points
        parts.append({"part": name, "points": round(points, 1), "of": max_points, "detail": detail})

    if access:
        crawlers = access.get("crawlers", [])
        for group, key in (("search", "ai_search_allowed"), ("fetch", "ai_fetch_allowed")):
            n, total = _allowed([c for c in crawlers if c["group"] == group])
            if total:
                part(key, w[key] * n / total, w[key], f"{n} of {total} AI {group} crawlers allowed")
        firewall = [c["token"] for c in crawlers if c["group"] in ("search", "fetch") and c["verdict"] == "refused by server"]
        part("no_firewall_refusal", 0 if firewall else w["no_firewall_refusal"], w["no_firewall_refusal"],
             "refused by the server: " + ", ".join(firewall) if firewall else "no AI search or fetch crawler refused by the server")
        llms = bool(access.get("llms_txt", {}).get("llms.txt", {}).get("present"))
        part("llms_txt", w["llms_txt"] if llms else 0, w["llms_txt"], "llms.txt present" if llms else "no llms.txt")
    if traffic:
        by_bot = traffic.get("by_bot", [])
        ai = sum(b["hits"] for b in by_bot if b.get("kind") == "ai" and b.get("group") in ("search", "fetch"))
        se = sum(b["hits"] for b in by_bot if b.get("kind") == "listed" and b.get("group") == "search engine")
        part("ai_hits_seen", w["ai_hits_seen"] if ai else 0, w["ai_hits_seen"], f"{ai} AI search and fetch hits in the traffic period")
        part("search_engine_hits_seen", w["search_engine_hits_seen"] if se else 0, w["search_engine_hits_seen"],
             f"{se} search-engine hits in the traffic period")
    points = sum(p["points"] for p in parts)
    score = round(100 * points / measured_max) if measured_max else None
    return {"score": score, "points": round(points, 1), "measured_max": measured_max, "parts": parts}


# --- gaps and opportunity -------------------------------------------------------------------------

def site_gaps(access: dict | None, traffic: dict | None, scan_results: list[dict], weights: dict) -> list[dict]:
    gaps = []
    if access:
        for c in access.get("crawlers", []):
            if c["group"] in ("search", "fetch") and c["verdict"].startswith("refused"):
                gaps.append({"kind": "ai crawler refused", "detail": f"{c['token']} ({c['operator']}, {c['group']}): {c['verdict']}"})
        if not access.get("llms_txt", {}).get("llms.txt", {}).get("present"):
            gaps.append({"kind": "no llms.txt", "detail": "the site has no /llms.txt"})
    if traffic:
        share = traffic.get("unknown_agent_share") or 0
        if share > weights["gaps"]["unknown_agent_share"]:
            gaps.append({"kind": "unknown agents", "detail": f"{share:.0%} of hits are automated agents on no list"})
        for b in traffic.get("by_bot", []):
            st = b.get("status") or {}
            bad = {k: v for k, v in st.items() if k in ("4xx", "5xx")}
            if bad:
                gaps.append({"kind": "errors shown to crawlers", "detail": f"{b['bot']}: " + ", ".join(f"{v} {k}" for k, v in sorted(bad.items()))
                             + f" of {sum(st.values())} responses"})
        seen = {b["bot"] for b in traffic.get("by_bot", []) if b.get("hits")}
        missing = [c["token"] for c in (access or {}).get("crawlers", []) if c["group"] == "search" and c["token"] not in seen
                   and not c["verdict"].startswith("refused") and c.get("probe") != "not probed"]
        if access and missing:
            gaps.append({"kind": "allowed but not seen", "detail": "AI search crawlers allowed but absent from the traffic: " + ", ".join(missing)})
    for r in scan_results:
        how = (r.get("evidence") or {}).get("fetch", {}).get("how")
        if how in ("firecrawl", "crawlee"):
            gaps.append({"kind": "needs rendering", "detail": f"{r.get('source')}: plain HTTP was not enough, read through {how}"})
        if r.get("findings"):
            gaps.append({"kind": "text aimed at AI", "detail": f"{r.get('source')}: {len(r['findings'])} finding(s)"})
    return gaps


def score(scan: list[dict] | None = None, access: dict | None = None, traffic: dict | None = None, weights: dict | None = None) -> dict:
    """All scores, one entry per site (by host). A traffic report applies to every site in the run."""
    weights = weights or load_weights()
    scan = scan or []
    access_reports = (access or {}).get("reports", [])
    hosts = sorted({_host(r.get("source", "")) for r in scan} | {_host(a["url"]) for a in access_reports}) or (["(traffic only)"] if traffic else [])
    sites = []
    for host in hosts:
        results = [r for r in scan if _host(r.get("source", "")) == host]
        acc = next((a for a in access_reports if _host(a["url"]) == host), None)
        pages = sorted((page_risk(r, weights) for r in results), key=lambda p: -p["score"])
        vis = site_visibility(acc, traffic, weights)
        worst = pages[0]["score"] if pages else 0
        o = weights["opportunity"]
        opportunity = round(o["visibility_gap"] * (100 - vis["score"]) + o["page_risk"] * worst) if vis["score"] is not None else None
        training = [c["token"] for c in (acc or {}).get("crawlers", []) if c["group"] == "training" and c["verdict"].startswith("refused")]
        sites.append({"site": host, "visibility": vis, "risk": {"max": worst, "pages": pages}, "opportunity": opportunity,
                      "training_crawlers_refused": training, "gaps": site_gaps(acc, traffic, results, weights)})
    sites.sort(key=lambda s: -(s["opportunity"] or 0))
    return {"tool": "pagevet-scores", "version": __version__, "score_version": weights["score_version"], "sites": sites,
            "note": "Ranking aids from deterministic rules and the weights in score_version; not detection rates."}


def render_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["site", "visibility", "risk_max", "opportunity", "pages", "gaps", "score_version"])
    for s in report["sites"]:
        w.writerow([s["site"], s["visibility"]["score"], s["risk"]["max"], s["opportunity"], len(s["risk"]["pages"]),
                    "; ".join(g["kind"] for g in s["gaps"]), report["score_version"]])
    return buf.getvalue()


def _read(path: str | None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pagevet.scores", description="Page risk, site AI visibility and opportunity scores from PageVet reports.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--scan", metavar="FILE", help="pagevet --format json report")
    parser.add_argument("--access", metavar="FILE", help="pagevet-access --format json report")
    parser.add_argument("--traffic", metavar="FILE", help="python -m pagevet.traffic JSON report")
    parser.add_argument("--weights", metavar="FILE", help="scoring weights (default: the packaged scoring.json)")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--out", metavar="FILE")
    args = parser.parse_args(argv)
    if not (args.scan or args.access or args.traffic):
        parser.error("give at least one of --scan, --access, --traffic")
    try:
        report = score(_read(args.scan), _read(args.access), _read(args.traffic), load_weights(args.weights))
    except (OSError, ValueError, KeyError) as exc:
        sys.stderr.write(f"pagevet.scores: {exc}" + "\n")
        return 2
    text = json.dumps(report, indent=1) + "\n" if args.format == "json" else render_csv(report)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
