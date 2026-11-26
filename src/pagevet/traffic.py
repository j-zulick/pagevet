"""AI-crawler visits from your own traffic data (0.3.0).

    python -m pagevet.traffic hits.csv --out traffic.json
    python -m pagevet.traffic access.log --format csv --out traffic.csv
    python -m pagevet.traffic export.json --input-format opensearch --ts-field timestamp --url-field request.path
    python -m pagevet.traffic access.log --updates updates.csv --out traffic.json
    python -m pagevet.traffic access.log --bots search-bots.csv          # also search-engine crawlers, from your own list

Three inputs:

- a CSV with a header ``date,url,user_agent,hits`` or ``date,url,bot,hits`` (``hits`` optional, default 1; any other
  column, an IP address included, is never read);
- a raw access log in the combined format (Apache and nginx's default); the client address is not kept;
- an OpenSearch (or Elasticsearch) export: a search-API response (``hits.hits[]._source``) or NDJSON, one document or
  ``{"_source": ...}`` per line. Field names are options (``--ts-field``, ``--url-field``, ``--ua-field``; defaults
  ``@timestamp``, ``url.path``, ``user_agent.original``) and may be dotted paths or flat dotted keys. Only those
  three fields are read.

Each hit's user agent is matched against PageVet's AI crawler list (``pagevet.access.CRAWLERS``) and, with
``--bots FILE``, an extra list in the same CSV format (``token,operator,group,user_agent``), for example
search-engine crawlers such as Googlebot or Bingbot. A row whose group is an AI group (``training``, ``search``,
``fetch``) counts as an AI crawler; any other group (``search engine``, say) is counted as a listed bot. The built-in
list wins when a token is on both. The output, as JSON or CSV, has per page and per crawler the hits, first seen and
last seen, with the crawler's group and kind (``ai`` or ``listed``), totals per crawler, and the **unknown-agent
share**: hits whose user agent is empty, or looks automated (bot, crawler, spider, an HTTP library) without being on
either list, divided by all hits. Query strings are dropped from URLs, so search terms and tokens in
links are not kept.

``--updates FILE`` (``url,date``: the day each page's content changed; a path matches that path on any host) adds AI-crawler hits on that page in the 14
days before the update and in the 14 days from the update on. That is a signal, not proof: crawl schedules have
their own rhythm, and anyone can send a crawler's user-agent string (``pagevet-access`` probes rely on the same
string), so hits are claims made by the client, not verified visits.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pagevet import __version__
from pagevet.access import CRAWLERS, GROUPS

WINDOW_DAYS = 14
SIGNAL_NOTE = ("A signal, not proof: crawlers keep their own schedules, and a user-agent string is whatever the client "
               "sends, so these are claimed visits, not verified ones.")
AUTOMATED = re.compile(r"bot\b|bot/|crawl|spider|scrap|slurp|fetch|python-requests|python-urllib|aiohttp|httpx|curl/|wget/"
                       r"|go-http-client|okhttp|java/|libwww|headless|phantomjs|axios|node-fetch", re.I)
NOT_A_BOT = {"browser", "human", "none", "other", "user"}
OPENSEARCH_DEFAULTS = {"ts_field": "@timestamp", "url_field": "url.path", "ua_field": "user_agent.original"}


@dataclass(frozen=True)
class Hit:
    day: date
    url: str
    agent: str  # the user-agent string, or the bot name from a CSV ``bot`` column
    hits: int = 1
    named: bool = False  # True when ``agent`` is a bot name, not a user-agent string


# --- classification -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Bot:
    token: str
    operator: str
    group: str
    user_agent: str = ""
    ai: bool = True


def bot_list(extra: Iterable[dict] = ()) -> list[Bot]:
    """PageVet's AI crawlers, then the rows of an extra bots file whose token is not already listed."""
    bots = [Bot(c.token, c.operator, c.group, c.user_agent, True) for c in CRAWLERS]
    known = {b.token.lower() for b in bots}
    for row in extra:
        token = (row.get("token") or "").strip()
        if token and token.lower() not in known:
            group = (row.get("group") or "").strip()
            bots.append(Bot(token, (row.get("operator") or "").strip(), group, (row.get("user_agent") or "").strip(), group in GROUPS))
            known.add(token.lower())
    return bots


def read_bots(path: str) -> list[dict]:
    """Rows of a bots file: CSV with the header token,operator,group,user_agent (the AI crawler file's format)."""
    rows = list(csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8"))))
    if rows and not {"token", "group"} <= set(rows[0]):
        raise ValueError(f"{path}: a bots file needs the header token,operator,group,user_agent")
    return rows


DEFAULT_BOTS = bot_list()


class _Matcher:
    def __init__(self, bots: list[Bot]):
        self.by_token = {b.token.lower(): b for b in bots}
        self.visiting = sorted((b for b in bots if b.user_agent), key=lambda b: -len(b.token))  # longest token first


@lru_cache(maxsize=8)
def _matcher_for(bots: tuple[Bot, ...]) -> _Matcher:
    return _Matcher(list(bots))


def _matcher(bots: list[Bot] | None) -> _Matcher:
    return _matcher_for(tuple(bots or DEFAULT_BOTS))


def classify(agent: str, named: bool = False, bots: list[Bot] | None = None) -> tuple[str, str]:
    """Return (kind, token): ``ai`` or ``listed`` (token set), ``unknown`` (empty or automated, on no list) or ``other``."""
    m = _matcher(bots)
    a = (agent or "").strip()
    if not a or a == "-":
        return "unknown", ""
    low = a.lower()
    if named:
        if low in m.by_token:
            b = m.by_token[low]
            return ("ai" if b.ai else "listed"), b.token
        if low in NOT_A_BOT:
            return "other", ""
    for b in m.visiting:
        if b.token.lower() in low:
            return ("ai" if b.ai else "listed"), b.token
    if named or AUTOMATED.search(a):
        return "unknown", ""
    return "other", ""


# --- reading --------------------------------------------------------------------------------------

def _day(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):  # epoch seconds or milliseconds
        secs = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(secs, UTC).date()
    text = str(value).strip()
    if re.fullmatch(r"\d{10,13}", text):
        return _day(int(text))
    m = re.match(r"(\d{2}/\w{3}/\d{4}):(\d{2}:\d{2}:\d{2}) ([+-]\d{4})", text)  # access-log time, e.g. 10/Oct/2026:13:55:36 -0700
    if m:
        return datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%d/%b/%Y %H:%M:%S %z").astimezone(UTC).date()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed.astimezone(UTC) if parsed.tzinfo else parsed).date()


def _path(url: str) -> str:
    """The URL without query string or fragment; a full URL keeps scheme and host."""
    url = (url or "").strip()
    p = urlsplit(url)
    if p.scheme and p.netloc:
        return f"{p.scheme}://{p.netloc}{p.path or '/'}"
    return p.path or "/"


def read_csv(text: str) -> Iterator[Hit]:
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower(): f for f in reader.fieldnames or []}
    if "date" not in fields or "url" not in fields or not ({"user_agent", "bot"} & fields.keys()):
        raise ValueError("CSV needs a header with date, url and user_agent or bot (hits optional)")
    agent_col = fields.get("user_agent") or fields["bot"]
    named = "user_agent" not in fields
    for row in reader:
        day = _day(row.get(fields["date"]))
        if day is None:
            continue
        raw = (row.get(fields["hits"]) if "hits" in fields else "") or "1"
        try:
            n = int(float(raw))
        except ValueError:
            continue
        yield Hit(day, _path(row.get(fields["url"]) or ""), (row.get(agent_col) or "").strip(), n, named)


# host ident user [time] "request" status bytes "referer" "user agent"; the host is matched and thrown away
LOG_LINE = re.compile(r'^\S+ \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<request>(?:[^"\\]|\\.)*)" \d{3} \S+(?: "(?:[^"\\]|\\.)*" "(?P<ua>(?:[^"\\]|\\.)*)")?')


def read_access_log(text: str) -> Iterator[Hit]:
    for line in text.splitlines():
        m = LOG_LINE.match(line)
        if not m:
            continue
        day = _day(m.group("time"))
        parts = m.group("request").split()
        if day is None or len(parts) < 2:
            continue
        yield Hit(day, _path(parts[1]), (m.group("ua") or "").replace('\\"', '"'))


def _get(doc: dict, dotted: str) -> object:
    if dotted in doc:
        return doc[dotted]
    cur: object = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _documents(text: str) -> Iterator[dict]:
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            whole = json.loads(stripped)
        except json.JSONDecodeError:
            whole = None
        if isinstance(whole, dict):
            if isinstance(whole.get("hits"), dict):
                for h in whole["hits"].get("hits", []):
                    yield h.get("_source", h)
                return
            yield whole.get("_source", whole)
            return
    if stripped.startswith("["):
        for d in json.loads(stripped):
            yield d.get("_source", d)
        return
    for line in text.splitlines():
        if line.strip():
            d = json.loads(line)
            yield d.get("_source", d) if isinstance(d, dict) else {}


def read_opensearch(text: str, ts_field: str = OPENSEARCH_DEFAULTS["ts_field"], url_field: str = OPENSEARCH_DEFAULTS["url_field"],
                    ua_field: str = OPENSEARCH_DEFAULTS["ua_field"]) -> Iterator[Hit]:
    for doc in _documents(text):
        day = _day(_get(doc, ts_field))
        url = _get(doc, url_field)
        if day is None or not url:
            continue
        yield Hit(day, _path(str(url)), str(_get(doc, ua_field) or ""))


def detect_format(path: str, text: str) -> str:
    name = path.lower()
    head = text.lstrip()[:2000]
    if name.endswith((".json", ".ndjson", ".jsonl")) or head.startswith(("{", "[")):
        return "opensearch"
    if name.endswith(".csv") or re.match(r"(?i)\s*\"?date\"?\s*,", head):
        return "csv"
    return "log"


def read(path: str, input_format: str = "auto", **fields: str) -> list[Hit]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    fmt = detect_format(path, text) if input_format == "auto" else input_format
    if fmt == "csv":
        return list(read_csv(text))
    if fmt == "log":
        return list(read_access_log(text))
    if fmt == "opensearch":
        return list(read_opensearch(text, **{k: v for k, v in fields.items() if v}))
    raise ValueError(f"unknown input format {fmt!r}")


def read_updates(path: str) -> list[tuple[str, date]]:
    rows = []
    for row in csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8"))):
        day = _day(row.get("date"))
        if row.get("url") and day:
            rows.append((_path(row["url"]), day))
    return rows


# --- summary --------------------------------------------------------------------------------------

def summarize(hits: Iterable[Hit], updates: list[tuple[str, date]] | None = None, bots: list[Bot] | None = None) -> dict:
    """Return the traffic report as a dict (see the module docstring)."""
    hits = list(hits)
    by_token = _matcher(bots).by_token
    total = ai = listed = unknown = 0
    pages: dict[tuple[str, str], list] = {}
    for h in hits:
        kind, token = classify(h.agent, h.named, bots)
        total += h.hits
        if kind == "unknown":
            unknown += h.hits
        if kind not in ("ai", "listed"):
            continue
        if kind == "ai":
            ai += h.hits
        else:
            listed += h.hits
        slot = pages.setdefault((h.url, token), [0, h.day, h.day])
        slot[0] += h.hits
        slot[1], slot[2] = min(slot[1], h.day), max(slot[2], h.day)
    rows = []
    for (url, token), (n, first, last) in sorted(pages.items(), key=lambda kv: (-kv[1][0], kv[0])):
        b = by_token[token.lower()]
        rows.append({"url": url, "bot": token, "operator": b.operator, "group": b.group, "kind": "ai" if b.ai else "listed", "hits": n,
                     "first_seen": first.isoformat(), "last_seen": last.isoformat()})
    by_bot: dict[str, dict] = {}
    for r in rows:
        b = by_bot.setdefault(r["bot"], {"bot": r["bot"], "operator": r["operator"], "group": r["group"], "kind": r["kind"], "hits": 0,
                                         "pages": 0, "first_seen": r["first_seen"], "last_seen": r["last_seen"]})
        b["hits"] += r["hits"]
        b["pages"] += 1
        b["first_seen"], b["last_seen"] = min(b["first_seen"], r["first_seen"]), max(b["last_seen"], r["last_seen"])
    days = [h.day for h in hits]
    report: dict = {
        "tool": "pagevet.traffic", "version": __version__,
        "period": {"first": min(days).isoformat(), "last": max(days).isoformat()} if days else None,
        "total_hits": total, "ai_hits": ai, "listed_bot_hits": listed, "unknown_agent_hits": unknown,
        "unknown_agent_share": round(unknown / total, 4) if total else None,
        "by_bot": sorted(by_bot.values(), key=lambda b: (-b["hits"], b["bot"])),
        "pages": rows,
        "note": "User agents are claims made by the client and can be faked; query strings are dropped.",
    }
    if updates is not None:
        report["updates"] = update_windows(hits, updates, bots=bots)
        report["updates_note"] = SIGNAL_NOTE
    return report


def _same_page(hit_url: str, update_url: str) -> bool:
    """An update given as a path matches that path on any host; a full URL must match exactly."""
    if "://" in update_url:
        return hit_url == update_url
    return (urlsplit(hit_url).path or "/") == update_url


def update_windows(hits: list[Hit], updates: list[tuple[str, date]], days: int = WINDOW_DAYS, bots: list[Bot] | None = None) -> list[dict]:
    """AI-crawler hits on each updated page in the ``days`` before the update and the ``days`` from it on."""
    seen = [h.day for h in hits]
    lo, hi = (min(seen), max(seen)) if seen else (None, None)
    out = []
    for url, day in updates:
        before_start, after_end = day - timedelta(days=days), day + timedelta(days=days - 1)
        before = after = 0
        by_bot: dict[str, list[int]] = {}
        for h in hits:
            if not _same_page(h.url, url):
                continue
            kind, token = classify(h.agent, h.named, bots)
            if kind != "ai":
                continue
            if before_start <= h.day < day:
                before += h.hits
                by_bot.setdefault(token, [0, 0])[0] += h.hits
            elif day <= h.day <= after_end:
                after += h.hits
                by_bot.setdefault(token, [0, 0])[1] += h.hits
        complete = lo is not None and lo <= before_start and hi >= after_end
        out.append({"url": url, "date": day.isoformat(), "window_days": days, "ai_hits_before": before, "ai_hits_after": after,
                    "by_bot": {b: {"before": v[0], "after": v[1]} for b, v in sorted(by_bot.items())},
                    "data_covers_both_windows": complete})
    return out


def render_json(report: dict) -> str:
    return json.dumps(report, indent=1) + "\n"


def render_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["url", "bot", "operator", "group", "kind", "hits", "first_seen", "last_seen"])
    for r in report["pages"]:
        w.writerow([r["url"], r["bot"], r["operator"], r["group"], r.get("kind", "ai"), r["hits"], r["first_seen"], r["last_seen"]])
    share = report["unknown_agent_share"]
    w.writerow([])
    w.writerow(["total_hits", report["total_hits"], "ai_hits", report["ai_hits"], "listed_bot_hits", report.get("listed_bot_hits", 0),
                "unknown_agent_share", "" if share is None else share])
    if "updates" in report:
        w.writerow([])
        w.writerow(["updated_url", "update_date", "ai_hits_before_14d", "ai_hits_after_14d", "data_covers_both_windows"])
        for u in report["updates"]:
            w.writerow([u["url"], u["date"], u["ai_hits_before"], u["ai_hits_after"], u["data_covers_both_windows"]])
        w.writerow([SIGNAL_NOTE])
    return buf.getvalue()


def load(path: str, updates: str | None = None, input_format: str = "auto", bots: str | None = None, **fields: str) -> dict:
    """Read a traffic file (with an updates file and an extra bots file) and return the report; used by the visibility report too."""
    bot_rows = bot_list(read_bots(bots)) if bots else None
    return summarize(read(path, input_format, **fields), read_updates(updates) if updates else None, bot_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pagevet.traffic", description="AI-crawler visits from your own traffic data.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("file", help="CSV, combined-format access log, or OpenSearch export (JSON or NDJSON)")
    parser.add_argument("--input-format", choices=("auto", "csv", "log", "opensearch"), default="auto")
    parser.add_argument("--ts-field", default=OPENSEARCH_DEFAULTS["ts_field"], help="OpenSearch timestamp field (default %(default)s)")
    parser.add_argument("--url-field", default=OPENSEARCH_DEFAULTS["url_field"], help="OpenSearch URL field (default %(default)s)")
    parser.add_argument("--ua-field", default=OPENSEARCH_DEFAULTS["ua_field"], help="OpenSearch user-agent field (default %(default)s)")
    parser.add_argument("--updates", metavar="FILE", help="CSV url,date of content updates: AI-crawler hits 14 days before and after")
    parser.add_argument("--bots", metavar="FILE", help="extra crawlers to classify (CSV token,operator,group,user_agent), e.g. search engines")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--out", metavar="FILE")
    args = parser.parse_args(argv)
    try:
        report = load(args.file, args.updates, args.input_format, args.bots, ts_field=args.ts_field, url_field=args.url_field, ua_field=args.ua_field)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"pagevet.traffic: {exc}\n")
        return 2
    text = (render_csv if args.format == "csv" else render_json)(report)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
