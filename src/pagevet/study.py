"""Field studies: what the pages behind a topic's search results serve to AI models.

    pagevet-study run "running shoes" --from-json search-results.json --out docs/bench/2026-11-23-field-running-shoes
    pagevet-study report docs/bench/2026-11-23-field-running-shoes      # rewrite README.md from the saved data
    pagevet-study compare docs/bench/*-field-* --out docs/bench/FIELD-STUDIES.md
    pagevet-study explore docs/bench/*-field-* --out site/                # the faceted explorer (docs/EXPLORER.md)

``run`` builds the URL list (``pagevet-discover``: from saved search results, or SearXNG with
``--queries``), scans every page as a browser and as three AI crawlers (``--compare-agents``,
``--fetch-css``, robots.txt respected), and writes ``search-results.json``, ``urls.txt``,
``results.json`` and a README with the method, counts and limits. Every number in the README is
computed from ``results.json`` by :func:`summarize`, so ``report`` can regenerate it at any time.
Interpretation is left to a "What this says" section the author writes by hand (kept between
the markers on regeneration).

Pages that refuse PageVet are reported as not read; they are never retried through another
crawler.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pagevet import __version__

AGENTS = ("GPTBot", "ClaudeBot", "PerplexityBot")
EXPLORER_URL = "https://j-zulick.github.io/pagevet/"  # GitHub Pages, published on release (docs/EXPLORER.md)
NOTES_START = "<!-- notes: written by hand, kept by `pagevet-study report` -->"
NOTES_END = "<!-- end notes -->"
_STATUS = re.compile(r"'(\d{3})\s")


def _reason(error: str) -> str:
    """Return a short reason a page was not read."""
    match = _STATUS.search(error)
    if match:
        return f"HTTP {match.group(1)}"
    lowered = error.lower()
    if "robots.txt" in lowered:
        return "robots.txt disallows PageVet"
    if "name or service not known" in lowered or "nodename nor servname" in lowered or "getaddrinfo" in lowered or "connecterror" in lowered:
        return "could not connect"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    return "other error"


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the study's counts from a ``--format json`` report."""
    read = [r for r in results if not r.get("error")]
    unread = Counter(_reason(r["error"]) for r in results if r.get("error"))
    hidden: Counter = Counter()
    hidden_pages: list[dict[str, Any]] = []
    refusals: dict[str, Counter] = {a: Counter() for a in AGENTS}
    refused_any = refused_all = 0
    differs: list[str] = []
    cloaked: list[str] = []
    share_pages: list[str] = []
    share_flagged: list[str] = []
    assistants: Counter = Counter()
    for r in read:
        if r.get("ai_share_links"):
            share_pages.append(r["source"])
            assistants.update({link["assistant"] for link in r["ai_share_links"]})
        if any(f["channel"] == "AI share links" for f in r["findings"]):
            share_flagged.append(r["source"])
        own = [f for f in r["findings"] if not f["channel"].startswith("served to ")]
        if own:
            top = max(own, key=lambda f: ("low", "medium", "high").index(f["severity"]) if f["severity"] in ("low", "medium", "high") else -1)
            hidden[top["severity"]] += 1
            hidden_pages.append({"source": r["source"], "severity": top["severity"], "channel": top["channel"], "kinds": top["kinds"]})
        refused = set()
        for f in r["findings"]:
            if not f["channel"].startswith("served to "):
                continue
            agent = f["channel"].removeprefix("served to ")
            if "fetch_differs" in f["kinds"] and agent in refusals:
                refusals[agent][_reason(f["excerpt"])] += 1
                refused.add(agent)
            elif "cloaked_instruction" in f["kinds"]:
                cloaked.append(r["source"])
            elif "content_differs" in f["kinds"]:
                differs.append(r["source"])
        refused_any += bool(refused)
        refused_all += len(refused) == len(AGENTS)
    return {
        "scanned": len(results), "read": len(read), "unread": dict(unread.most_common()),
        "pages_with_findings": dict(hidden), "finding_pages": hidden_pages,
        "refused_any": refused_any, "refused_all": refused_all,
        "refusals": {a: dict(c.most_common()) for a, c in refusals.items()},
        "content_differs": sorted(set(differs)), "cloaked_instruction": sorted(set(cloaked)),
        # 1.1.0: AI share links, counted only when the results carry them (studies run with 1.1.0 or later)
        "share_tested": any("ai_share_links" in r for r in results), "share_pages": share_pages,
        "share_flagged": share_flagged, "share_assistants": dict(assistants.most_common()),
    }


def _share(part: int, whole: int) -> str:
    return f"{part} of {whole}" + (f" ({part / whole:.0%})" if whole else "")


def render(topic: str, queries: list[str], summary: dict[str, Any], *, date: str, version: str, search_count: int,
           max_per_host: int, notes: str = "", via: str = "http") -> str:
    """Return the study's README."""
    s = summary
    lines = [f"# Field study: {topic} ({date})", "",
             f"Pages a web search returns for {topic}, scanned for text aimed at AI models and for pages that treat AI crawlers "
             "differently from a browser. Every number below is computed from `results.json` by `pagevet-study report`.", "",
             f"Filter these pages by outcome, crawler and finding in the [field-study explorer]({EXPLORER_URL}#{urlencode([('ds', 'field'), ('f.study', topic)])}) "
             "(or offline: `pagevet-study explore --out site/`).", "",
             "## Method", "",
             f"- **Queries ({len(queries)}):** " + "; ".join(queries) + ".",
             f"- **Search results:** {search_count} URLs, saved in [`search-results.json`](search-results.json).",
             f"- **URL list:** `pagevet-discover --from-json search-results.json --max-per-host {max_per_host}` → {s['scanned']} URLs "
             "([`urls.txt`](urls.txt)).",
             f"- **Scan:** PageVet {version}, `pagevet --urls urls.txt --fetch-css --compare-agents"
             + (" --via firecrawl" if via == "firecrawl" else "") + " --format json`, robots.txt respected"
             + (" (pages rendered by a self-hosted Firecrawl after their scripts ran; the crawler comparison fetches plain HTML "
                "with each crawler's user agent)" if via == "firecrawl" else "") + ". Results: [`results.json`](results.json).", "",
             "## Results", "", "| | Pages |", "|---|---:|", f"| URLs scanned | {s['scanned']} |", f"| Read | {s['read']} |"]
    lines += [f"| Not read: {reason} | {count} |" for reason, count in s["unread"].items()]
    found = s["pages_with_findings"]
    lines += ["", "**Text aimed at AI models** (pages read, by their most severe finding outside the crawler comparison):", ""]
    if found:
        lines += [f"- {sev}: {found.get(sev, 0)}" for sev in ("high", "medium", "low")]
        lines += [""] + [f"  - `{p['source']}`: {p['severity']}, {p['channel']} ({', '.join(p['kinds'])})" for p in s["finding_pages"][:20]]
    else:
        lines.append(f"- None found on the {s['read']} pages read.")
    if s.get("share_tested"):
        lines += ["", f"**AI share links** (links or buttons that open an AI assistant with a pre-filled prompt): "
                  f"{_share(len(s['share_pages']), s['read'])} readable pages have one"
                  + (" (" + ", ".join(f"{a} {n}" for a, n in s["share_assistants"].items()) + " pages)" if s["share_assistants"] else "")
                  + f"; {len(s['share_flagged'])} with a prompt that gives the assistant instructions (findings in the \"AI share links\" channel)."]
    lines += ["", f"**AI crawlers refused:** {_share(s['refused_any'], s['read'])} readable pages refuse at least one of "
              f"{', '.join(AGENTS)}; {s['refused_all']} refuse all three.", ""]
    reasons = sorted({r for a in AGENTS for r in s["refusals"][a]})
    if reasons:
        lines += ["| Response to the AI crawler | " + " | ".join(AGENTS) + " |", "|---|" + "---:|" * len(AGENTS)]
        lines += [f"| {r} | " + " | ".join(str(s["refusals"][a].get(r, 0)) for a in AGENTS) + " |" for r in reasons]
        lines.append("")
    lines += [f"**Different content for an AI crawler:** {len(s['content_differs'])} page(s) served a crawler visible text under 90% "
              "similar to the browser's copy" + (": " + ", ".join(f"`{u}`" for u in s["content_differs"][:10]) if s["content_differs"] else "")
              + ".", "", f"**Instructions served only to an AI crawler:** {len(s['cloaked_instruction'])}.", "",
              "## What this says", "", NOTES_START, notes.strip() or "(not written yet)", NOTES_END, "",
              "## Limits", "",
              f"- **Sample:** one day, one search engine, {s['scanned']} URLs. A field sample, not a census.",
              f"- **Unread pages:** {s['scanned'] - s['read']} pages were not read. Pages that refused PageVet were not retried through "
              "another crawler or a browser, and robots.txt was respected; hidden content on them is unmeasured.",
              ("- **Fetching:** rendered by Firecrawl, so text and buttons a script inserts are seen; the crawler comparison is plain HTML."
               if via == "firecrawl" else "- **Fetching:** HTML only, no JavaScript rendering; text a script inserts is not seen."),
              "- **Crawler comparison:** by user agent only, from one address. Cloaking by IP address looks identical, and a crawler's "
              "real IP ranges may be treated differently from PageVet's. Rotating ads or product modules can make content differ without "
              "intent.",
              "- **Detection:** \"none found\" means none of PageVet's patterns matched. Held-out catch rates are in "
              "[docs/EVASION.md](../../EVASION.md); reworded instructions are missed.", ""]
    return "\n".join(lines)


def _notes(readme: Path) -> str:
    if not readme.is_file():
        return ""
    text = readme.read_text(encoding="utf-8")
    if NOTES_START in text and NOTES_END in text:
        body = text.split(NOTES_START, 1)[1].split(NOTES_END, 1)[0].strip()
        return "" if body == "(not written yet)" else body
    return ""


def report(folder: str, version: str = "") -> str:
    """Regenerate ``folder``/README.md from its saved data, keeping the hand-written notes; return the text."""
    from pagevet import __version__

    base = Path(folder)
    meta = json.loads((base / "study.json").read_text(encoding="utf-8"))
    results = json.loads((base / "results.json").read_text(encoding="utf-8"))
    search = json.loads((base / "search-results.json").read_text(encoding="utf-8"))
    text = render(meta["topic"], list(search), summarize(results), date=meta["date"], version=version or meta.get("version", __version__),
                  search_count=sum(len(v) for v in search.values()), max_per_host=meta.get("max_per_host", 0),
                  notes=_notes(base / "README.md"), via=meta.get("via", "http"))
    (base / "README.md").write_text(text, encoding="utf-8")
    return text


def run(topic: str, search: dict[str, list[str]], out: str, *, max_per_host: int = 4, delay: float = 0.3,
        scan_main: Callable[..., int] | None = None, via: str = "http", **hooks: Any) -> dict[str, Any]:
    """Build the list, scan it, and write the study folder; return the summary."""
    from pagevet import __version__
    from pagevet import scan as scan_mod
    from pagevet.discover import write_list

    search = {q: [u for u in urls if str(u).startswith(("http://", "https://"))] for q, urls in search.items()}
    base = Path(out)
    base.mkdir(parents=True, exist_ok=True)
    (base / "search-results.json").write_text(json.dumps(search, indent=1) + "\n", encoding="utf-8")
    urls = write_list(search, str(base / "urls.txt"), max_per_host)
    if not urls:
        raise ValueError("no URLs to scan")
    meta: dict[str, Any] = {"topic": topic, "date": time.strftime("%Y-%m-%d"), "version": __version__,
                            "max_per_host": max_per_host, "delay": delay}
    if via == "firecrawl":  # 1.1.0: pages rendered through the maintainer's or your Firecrawl (PAGEVET_FIRECRAWL_URL)
        meta |= {"via": "firecrawl", "how": "Firecrawl (rendered)",
                 "how_detail": "rendered by a self-hosted Firecrawl, robots.txt respected, linked stylesheets read; compared with "
                               "GPTBot, ClaudeBot and PerplexityBot user agents over plain HTTP"}
    (base / "study.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    code = (scan_main or scan_mod.main)(["--urls", str(base / "urls.txt"), "--fetch-css", "--compare-agents", "--delay", str(delay),
                                         "--max-pages", str(len(urls)), "--format", "json", "--out", str(base / "results.json"),
                                         *(["--via", "firecrawl"] if via == "firecrawl" else [])], **hooks)
    if code not in (0, 1, 2):
        raise RuntimeError(f"the scan ended with exit code {code}")
    report(out)
    return summarize(json.loads((base / "results.json").read_text(encoding="utf-8")))


def compare(folders: list[str]) -> str:
    """Return one table across several study folders."""
    rows = ["# Field studies", "", "Each row is one study; details and limits are in its folder.", "",
            "| Study | Date | Scanned | Read | Pages with text aimed at AI (high / medium / low) | Refuse ≥1 AI crawler | Refuse all three "
            "| Different content |", "|---|---|---:|---:|---|---|---:|---:|"]
    for folder in folders:
        base = Path(folder)
        if not (base / "study.json").is_file() or not (base / "results.json").is_file():
            continue
        meta = json.loads((base / "study.json").read_text(encoding="utf-8"))
        s = summarize(json.loads((base / "results.json").read_text(encoding="utf-8")))
        found = s["pages_with_findings"]
        rows.append(f"| [{meta['topic']}]({base.name}/) | {meta['date']} | {s['scanned']} | {s['read']} | "
                    f"{found.get('high', 0)} / {found.get('medium', 0)} / {found.get('low', 0)} | {_share(s['refused_any'], s['read'])} | "
                    f"{s['refused_all']} | {len(s['content_differs'])} |")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None, **hooks: Any) -> int:
    """Run the command line; return the exit code."""
    from pagevet.config import load_env_file

    parser = argparse.ArgumentParser(prog="pagevet-study", description="Field studies of the pages behind a topic's search results.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="discover, scan and write a study folder")
    p.add_argument("topic", help='what the study is about, e.g. "running shoes"')
    p.add_argument("--from-json", metavar="FILE", help='saved search results: {"query": ["url", ...]}')
    p.add_argument("--queries", metavar="FILE", help="one query per line, searched through SearXNG (PAGEVET_SEARXNG_URL)")
    p.add_argument("--per-query", type=int, default=10)
    p.add_argument("--max-per-host", type=int, default=4)
    p.add_argument("--delay", type=float, default=0.3)
    p.add_argument("--out", required=True, metavar="FOLDER")
    p.add_argument("--via", choices=("http", "firecrawl"), default="http",
                   help="how to read pages: plain http (default) or your Firecrawl (rendered; PAGEVET_FIRECRAWL_URL)")
    p = sub.add_parser("report", help="rewrite a study's README.md from its saved data")
    p.add_argument("folder")
    p = sub.add_parser("explore", help="write the field-study explorer: one self-contained HTML page")
    p.add_argument("folders", nargs="*", help="study folders (default: docs/bench/*-field-*)")
    p.add_argument("--bench", default="docs/bench", metavar="DIR", help="where the false-alarm and benchmark results are (default: docs/bench)")
    p.add_argument("--out", default="site", metavar="DIR", help="output folder; the page is DIR/index.html (default: site)")
    p.add_argument("--commit", metavar="SHA", help="commit to show in the footer (default: git rev-parse --short HEAD)")
    p = sub.add_parser("compare", help="one table across several study folders")
    p.add_argument("folders", nargs="+")
    p.add_argument("--out", metavar="FILE")
    args = parser.parse_args(argv)
    load_env_file()
    if args.command == "report":
        report(args.folder)
        sys.stderr.write(f"pagevet-study: wrote {args.folder}/README.md\n")
        return 0
    if args.command == "explore":
        from pagevet.explore import explore

        folders = args.folders or sorted(str(p) for p in Path(args.bench).glob("*-field-*"))
        page = explore(folders, args.out, args.bench, args.commit)
        sys.stderr.write(f"pagevet-study: wrote {page} ({page.stat().st_size:,} bytes)\n")
        return 0
    if args.command == "compare":
        text = compare(args.folders)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    if args.from_json:
        search = {q: [u for u in urls if str(u).startswith(("http://", "https://"))]
                  for q, urls in json.loads(Path(args.from_json).read_text(encoding="utf-8")).items()}
    elif args.queries:
        from pagevet.discover import searxng_search

        get = hooks.pop("get", None)
        queries = [q.strip() for q in Path(args.queries).read_text(encoding="utf-8").splitlines() if q.strip() and not q.startswith("#")]
        search = {q: (searxng_search(q, args.per_query, get) if get else searxng_search(q, args.per_query)) for q in queries}
    else:
        parser.error("give --from-json or --queries")
    summary = run(args.topic, search, args.out, max_per_host=args.max_per_host, delay=args.delay, via=args.via, **hooks)
    sys.stderr.write(f"pagevet-study: {summary['read']} of {summary['scanned']} pages read; README in {args.out}\n")
    return 0
