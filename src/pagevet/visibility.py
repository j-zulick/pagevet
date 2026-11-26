"""AI visibility report (0.3.0): one self-contained HTML page per site.

    pagevet-access https://shop.example/ https://shop.example/pricing --report visibility.html
    pagevet-access https://shop.example/ --report visibility.html --traffic access.log --updates updates.csv
    pagevet-access https://shop.example/ --report visibility.html --scan-report scan.json

The page brings together, for the pages checked:

- crawler access per AI crawler: what robots.txt says, page signals (meta tags, ``X-Robots-Tag``) and what the
  server answered each crawler's user agent (firewall refusals), from ``pagevet.access.check``;
- PageVet's findings and AI share links: from ``--scan-report`` (a ``pagevet --format json`` report) when it covers
  the page, else from scanning the page's raw HTML once more with a browser user agent;
- the site's ``/llms.txt`` and ``/llms-full.txt``;
- with ``--traffic``, AI-crawler hits per page and per crawler from your own data (``pagevet.traffic``: a CSV, an
  access log, an OpenSearch export, or a JSON report written by ``python -m pagevet.traffic``), with ``--updates``
  the before-and-after table, and with ``--traffic-bots`` an extra crawler list (search engines, say);
- when a scan report's pages carry fetch details (``evidence.fetch``: ``{"how", "attempts", "ms"}``, raw or
  rendered and how it was read), those details per page. Pages without them show nothing there.

The text report goes to stdout as usual; the HTML is written as well. With pages on more than one site, each site
gets its own file: ``visibility.html`` becomes ``visibility-<host>.html``. No script runs in the output and all page
text is escaped. The flag names live in ``FLAGS`` only.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pagevet import __version__

FLAGS = {"report": "--report", "traffic": "--traffic", "updates": "--updates", "bots": "--traffic-bots", "scan_report": "--scan-report"}
MAX_TRAFFIC_ROWS = 200


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the visibility-report options to ``pagevet-access``."""
    g = parser.add_argument_group("AI visibility report")
    g.add_argument(FLAGS["report"], dest="report", metavar="FILE", help="also write a self-contained HTML visibility report per site")
    g.add_argument(FLAGS["traffic"], dest="traffic", metavar="FILE",
                   help="with the report: AI-crawler hits from a CSV, access log, OpenSearch export or pagevet.traffic JSON")
    g.add_argument(FLAGS["updates"], dest="updates", metavar="FILE", help="with --traffic: CSV url,date of content updates")
    g.add_argument(FLAGS["bots"], dest="traffic_bots", metavar="FILE",
                   help="with --traffic: extra crawlers to classify (CSV token,operator,group,user_agent), e.g. search engines")
    g.add_argument(FLAGS["scan_report"], dest="scan_report", metavar="FILE",
                   help="with the report: take findings, AI share links and fetch details from this pagevet --format json report")


# --- inputs ---------------------------------------------------------------------------------------

def load_traffic(path: str, updates: str | None = None, bots: str | None = None) -> dict:
    """A traffic report from a pagevet.traffic JSON report or a raw traffic file."""
    from pagevet import traffic

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        data = None
    if isinstance(data, dict) and data.get("tool") == "pagevet.traffic":
        if updates or bots:
            raise ValueError(f"{FLAGS['updates']} and {FLAGS['bots']} need the raw traffic file, not a report that is already summarized")
        return data
    return traffic.load(path, updates, bots=bots)


def load_scan_report(path: str) -> dict[str, dict]:
    """Pages of a ``pagevet --format json`` report, by source URL."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = data if isinstance(data, list) else data.get("pages", data.get("results", []))
    return {p["source"]: p for p in pages if isinstance(p, dict) and p.get("source")}


def scan_page(url: str, get: Callable[[str, str], Any]) -> dict:
    """Read the page's raw HTML once with a browser user agent and scan it."""
    from dataclasses import asdict

    from pagevet.access import BROWSER_UA
    from pagevet.scan import scan_text

    r = get(url, BROWSER_UA)
    if r.error or r.status >= 400:
        return {"source": url, "findings": [], "ai_share_links": [], "error": r.error or f"page answered {r.status}"}
    result = scan_text(url, r.text)
    return {"source": url, "findings": [asdict(f) for f in result.findings], "ai_share_links": result.ai_share_links, "error": result.error}


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _traffic_for(site: str, report: dict) -> dict:
    """Keep the traffic rows for ``site``: full URLs on that host, and paths (which carry no host)."""
    def mine(url: str) -> bool:
        return "://" not in url or _host(url) == site

    out = dict(report)
    out["pages"] = [r for r in report.get("pages", []) if mine(r["url"])]
    if "updates" in report:
        out["updates"] = [u for u in report["updates"] if mine(u["url"])]
    return out


def build(access_reports: list[Any], pages: dict[str, dict], traffic: dict | None = None) -> dict[str, dict]:
    """Group everything by site; return {host: data for render_html}."""
    sites: dict[str, dict] = {}
    for r in access_reports:
        site = sites.setdefault(_host(r.url) or r.url, {"site": _host(r.url) or r.url, "access": [], "pages": []})
        site["access"].append(r)
        site["pages"].append(pages.get(r.url, {"source": r.url, "findings": [], "ai_share_links": [], "error": ""}))
    for site in sites.values():
        site["traffic"] = _traffic_for(site["site"], traffic) if traffic else None
    return sites


# --- rendering ------------------------------------------------------------------------------------

_CSS = """:root{--fg:#1d2330;--muted:#5b6475;--line:#d9dde5;--bg:#fff;--soft:#f4f6f9;--accent:#1f5fbf;--warn:#9a3412;--diff:#fff3c4}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}
header{padding:16px 20px 8px;border-bottom:1px solid var(--line)}h1{font-size:1.35rem;margin:0 0 4px}h2{font-size:1.1rem;margin:22px 0 8px}
h3{font-size:.95rem;margin:14px 0 6px;overflow-wrap:anywhere}.sub{margin:0 0 10px;color:var(--muted)}
#headline{display:flex;flex-wrap:wrap;gap:10px;padding:12px 20px;background:var(--soft);border-bottom:1px solid var(--line)}
.stat{background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:11rem}.stat b{display:block;font-size:1.2rem}
.stat span{color:var(--muted);font-size:.85rem}main{padding:4px 20px 20px;max-width:90rem}
table{width:100%;border-collapse:collapse;font-size:.86rem;margin:4px 0 10px}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--soft)}td{overflow-wrap:anywhere}tr.warn td{background:var(--diff)}.num{text-align:right;font-variant-numeric:tabular-nums}
.f{border-left:4px solid #999;background:var(--soft);margin:6px 0;padding:6px 10px}.f.high{border-color:#b3261e}.f.medium{border-color:#c77700}
.note{color:var(--muted);font-size:.85rem}.empty{color:var(--muted);font-style:italic}code{background:var(--soft);padding:0 3px;border-radius:3px}
footer{padding:12px 20px;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem}"""


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _table(head: list[str], rows: list[list[object]], warn: list[bool] | None = None, num: set[int] | None = None) -> str:
    num = num or set()
    th = "".join(f"<th{' class=num' if i in num else ''}>{_e(h)}</th>" for i, h in enumerate(head))
    body = "".join(
        f"<tr{' class=warn' if warn and warn[k] else ''}>" + "".join(f"<td{' class=num' if i in num else ''}>{_e(c)}</td>" for i, c in enumerate(row)) + "</tr>"
        for k, row in enumerate(rows))
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _access(r: Any) -> str:
    from pagevet.access import GROUP_LABEL

    meta = f"robots.txt {_e(r.robots_txt)}; browser status {_e(r.browser_status)}" + (f"; <b>{_e(r.error)}</b>" if r.error else "")
    rows = [[c.token, c.operator, GROUP_LABEL[c.group], f"{c.robots}: {c.robots_rule}", " ".join(c.page_signals) or "none",
             c.probe + (f" ({c.status})" if c.status and c.probe == "served" else ""), c.verdict, c.note] for c in r.crawlers]
    warn = [c.verdict == "refused by server" for c in r.crawlers]
    summary = "; ".join(f"{GROUP_LABEL[g]}: {v}" for g, v in r.summary().items())
    return (f"<h3>{_e(r.url)}</h3><p class=note>{meta}. {_e(summary)}.</p>"
            + _table(["Crawler", "Operator", "Use", "robots.txt", "Page signals (meta, X-Robots-Tag)", "Firewall (server answer)", "Verdict", "Note"],
                     rows, warn))


def _findings(page: dict) -> str:
    src = _e(page.get("source"))
    if page.get("error"):
        return f"<h3>{src}</h3><p class=empty>Not read: {_e(page['error'])}</p>"
    found = "".join(f'<div class="f {_e(f.get("severity"))}"><b>{_e(f.get("severity"))}</b> · {_e(f.get("channel"))} · '
                    f'{_e(", ".join(f.get("kinds", [])))}{" · commercial" if f.get("intent") else ""}<br>{_e(f.get("excerpt"))}</div>'
                    for f in page.get("findings", [])) or "<p class=empty>No findings. Pattern matching only: a clean result is not proof a page is safe.</p>"
    links = page.get("ai_share_links") or []
    share = (_table(["Assistant", "Label", "Pre-filled prompt"], [[s.get("assistant"), s.get("label"), s.get("prompt")] for s in links])
             if links else "<p class=note>No AI share links.</p>")
    return f"<h3>{src}</h3>{found}<p class=note>AI share links (links that open an AI assistant with a pre-filled prompt):</p>{share}"


def _llms(r: Any) -> str:
    rows = []
    for name in ("llms.txt", "llms-full.txt"):
        e = r.llms_txt.get(name, {})
        rows.append([f"/{name}", "present" if e.get("present") else "absent", e.get("status"), e.get("title", ""), e.get("links", ""),
                     e.get("bytes", ""), {True: "yes", False: "no"}.get(e.get("follows_format"), "")])
    return _table(["File", "State", "Status", "Title", "Links", "Bytes", "Starts with a # title"], rows, num={4, 5})


def _traffic(t: dict) -> str:
    share = t.get("unknown_agent_share")
    period = t.get("period") or {}
    head = (f"<p class=note>{_e(t.get('total_hits'))} hits from {_e(period.get('first'))} to {_e(period.get('last'))}; "
            f"{_e(t.get('ai_hits'))} from AI crawlers" + (f", {_e(t.get('listed_bot_hits'))} from other listed crawlers" if t.get("listed_bot_hits") else "")
            + f"; unknown-agent share {'n/a' if share is None else f'{share:.1%}'} "
            "(empty or automated user agents not on PageVet's list). User agents can be faked: these are claimed visits.</p>")
    bots = _table(["Crawler", "Operator", "Group", "Kind", "Hits", "Pages", "First seen", "Last seen"],
                  [[b["bot"], b["operator"], b["group"], b.get("kind", "ai"), b["hits"], b["pages"], b["first_seen"], b["last_seen"]]
                   for b in t.get("by_bot", [])], num={4, 5})
    rows = t.get("pages", [])
    more = f"<p class=note>First {MAX_TRAFFIC_ROWS} of {len(rows)} rows.</p>" if len(rows) > MAX_TRAFFIC_ROWS else ""
    pages = _table(["Page", "Crawler", "Group", "Hits", "First seen", "Last seen"],
                   [[r["url"], r["bot"], r["group"], r["hits"], r["first_seen"], r["last_seen"]] for r in rows[:MAX_TRAFFIC_ROWS]], num={3})
    out = head + "<h3>By crawler</h3>" + bots + "<h3>By page and crawler</h3>" + pages + more
    if t.get("updates") is not None:
        ups = _table(["Page", "Updated", "AI hits, 14 days before", "AI hits, 14 days from the update", "Data covers both windows"],
                     [[u["url"], u["date"], u["ai_hits_before"], u["ai_hits_after"], "yes" if u["data_covers_both_windows"] else "no"] for u in t["updates"]],
                     num={2, 3})
        out += f"<h3>Before and after content updates</h3>{ups}<p class=note>{_e(t.get('updates_note', ''))}</p>"
    return out


def fetch_details(page: dict) -> dict | None:
    """The page's fetch block: ``evidence.fetch`` (``{"how", "attempts", "ms"}``), or a top-level ``fetch``."""
    block = (page.get("evidence") or {}).get("fetch") if isinstance(page.get("evidence"), dict) else None
    block = block if isinstance(block, dict) else page.get("fetch")
    return block if isinstance(block, dict) else None


def _attempts(attempts: object) -> str:
    """The chain's steps (``{"via", "ok", "ms", "reason"}`` each) as one line; a number or text is shown as it is."""
    if not isinstance(attempts, list):
        return "" if attempts is None else str(attempts)
    steps = []
    for a in attempts:
        if isinstance(a, dict):
            reason = f" ({a['reason']})" if a.get("reason") else ""
            steps.append(f"{a.get('via', '?')}: {'ok' if a.get('ok') else 'failed'}{reason}")
    return "; ".join(steps)


def _fetch(pages: list[dict]) -> str:
    rows = [[p["source"], f.get("how"), _attempts(f.get("attempts")), f.get("ms")] for p in pages if (f := fetch_details(p))]
    if not rows:
        return ""
    return ("<h2>How each page was read</h2><p class=note>Raw HTML or rendered (after scripts ran), from the scan report.</p>"
            + _table(["Page", "How", "Attempts", "ms"], rows, num={3}))


def render_html(data: dict, generated: str | None = None) -> str:
    """Return the visibility report for one site as a complete HTML document."""
    from pagevet.access import GROUP_LABEL, GROUPS

    generated = generated or datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    access, pages, t = data["access"], data["pages"], data.get("traffic")
    first = access[0]
    findings = sum(len(p.get("findings", [])) for p in pages)
    firewall = sum(c.verdict == "refused by server" for r in access for c in r.crawlers)
    stats = [(GROUP_LABEL[g].capitalize(), first.summary()[g]) for g in GROUPS]
    stats += [("Firewall refusals", firewall), ("llms.txt", "present" if first.llms_txt.get("llms.txt", {}).get("present") else "absent"),
              ("Findings", findings), ("AI share links", sum(len(p.get("ai_share_links") or []) for p in pages))]
    if t:
        stats.append(("AI-crawler hits", t.get("ai_hits")))
    cards = "".join(f"<div class=stat><b>{_e(v)}</b><span>{_e(k)}</span></div>" for k, v in stats)
    traffic = f"<h2>AI-crawler traffic</h2>{_traffic(t)}" if t else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI visibility: {_e(data['site'])}</title>
<style>{_CSS}</style></head><body>
<header><h1>AI visibility: {_e(data['site'])}</h1>
<p class=sub>{len(access)} page(s) · generated {_e(generated)} · PageVet {_e(__version__)}. The three access cards are for {_e(first.url)}; the other cards count all pages.</p></header>
<section id=headline>{cards}</section>
<main>
<h2>Crawler access</h2>
<p class=note>robots.txt per RFC 9309, page-level signals, and what the server answered each crawler's user agent. A highlighted row is a
firewall refusal: robots.txt allows the crawler but the server refused it.</p>
{''.join(_access(r) for r in access)}
<h2>Findings and AI share links</h2>
{''.join(_findings(p) for p in pages)}
<h2>llms.txt</h2>
{_llms(first)}
{traffic}
{_fetch(pages)}
</main>
<footer>Probes send each crawler's user-agent string, not its IP addresses, so a site that verifies crawlers by IP may answer the real crawler
differently. Findings come from pattern matching. Made with PageVet {_e(__version__)}.</footer></body></html>
"""


def _paths(out: str, sites: list[str]) -> dict[str, Path]:
    p = Path(out)
    if len(sites) == 1:
        return {sites[0]: p}
    return {s: p.with_name(f"{p.stem}-{s.replace(':', '_')}{p.suffix or '.html'}") for s in sites}


def write(args: argparse.Namespace, access_reports: list[Any], get: Callable[[str, str], Any]) -> int:
    """Write the visibility report(s) for ``pagevet-access``; return 0, or 2 on a bad input file."""
    if not getattr(args, "report", None):
        if any(getattr(args, k, None) for k in ("traffic", "updates", "traffic_bots", "scan_report")):
            sys.stderr.write(f"pagevet-access: {FLAGS['traffic']}, {FLAGS['updates']}, {FLAGS['bots']} and {FLAGS['scan_report']} need {FLAGS['report']}\n")
            return 2
        return 0
    try:
        traffic = load_traffic(args.traffic, args.updates, args.traffic_bots) if args.traffic else None
        if (args.updates or args.traffic_bots) and not args.traffic:
            raise ValueError(f"{FLAGS['updates']} and {FLAGS['bots']} need {FLAGS['traffic']}")
        scanned = load_scan_report(args.scan_report) if args.scan_report else {}
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"pagevet-access: visibility report: {exc}\n")
        return 2
    pages = {r.url: scanned.get(r.url) or scan_page(r.url, get) for r in access_reports if r.crawlers}
    sites = build([r for r in access_reports if r.crawlers], pages, traffic)
    for site, path in _paths(args.report, list(sites)).items():
        path.write_text(render_html(sites[site]), encoding="utf-8")
        sys.stderr.write(f"pagevet-access: visibility report for {site} written to {path}\n")
    return 0
