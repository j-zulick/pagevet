"""Load PageVet reports into Supabase (Postgres) through its REST API (PostgREST). Standard library only.

    python integrations/supabase/load.py --traffic traffic.json --scan scan.json --access access.json --scores scores.json --dry-run
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python integrations/supabase/load.py --traffic traffic.json

Create the tables first with `schema.sql`. Rows are upserts keyed on each table's primary key, so loading the same
report twice changes nothing. The service-role key bypasses row level security: keep it server-side (a Windmill or
n8n job, your own machine), never in a browser or a public repo. `--dry-run` prints the rows and sends nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

CONFLICT = {
    "pagevet_bots": "token",
    "pagevet_bot_hits": "period_start,period_end,url,bot",
    "pagevet_findings": "id",
    "pagevet_crawler_access": "url,token,checked_on",
    "pagevet_scores": "site,scored_on,score_version",
}
BATCH = 500


def bot_rows(traffic: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for b in traffic.get("by_bot", []):
        seen[b["bot"]] = {"token": b["bot"], "operator": b.get("operator", ""), "bot_group": b.get("group", ""), "kind": b.get("kind", "ai")}
    return list(seen.values())


def hit_rows(traffic: dict) -> list[dict]:
    period = traffic.get("period") or {}
    start, end = period.get("first"), period.get("last")
    return [{"period_start": start, "period_end": end, "url": r["url"], "bot": r["bot"], "hits": r["hits"],
             "first_seen": r.get("first_seen"), "last_seen": r.get("last_seen")} for r in traffic.get("pages", [])]


def finding_rows(scan: list[dict]) -> list[dict]:
    rows = []
    for result in scan:
        url = result.get("source", "")
        when = (result.get("evidence") or {}).get("fetched_at")
        for f in result.get("findings", []):
            key = "\n".join([url, f.get("channel", ""), ",".join(f.get("kinds", [])), f.get("excerpt", "")])
            tax = f.get("taxonomy") or {}
            rows.append({"id": hashlib.sha256(key.encode()).hexdigest(), "url": url, "scanned_at": when, "channel": f.get("channel", ""),
                         "kinds": f.get("kinds", []), "severity": f.get("severity", "low"), "intent": f.get("intent", ""),
                         "excerpt": f.get("excerpt", ""), "owasp": tax.get("owasp", []), "atlas": tax.get("atlas", [])})
    return rows


def access_rows(access: dict, today: str) -> list[dict]:
    return [{"url": r["url"], "token": c["token"], "checked_on": today, "bot_group": c["group"], "verdict": c["verdict"],
             "robots": c["robots"], "probe": c["probe"], "status": c.get("status")}
            for r in access.get("reports", []) for c in r.get("crawlers", [])]


def score_rows(scores: dict, today: str) -> list[dict]:
    return [{"site": s["site"], "scored_on": today, "score_version": scores["score_version"], "visibility": s["visibility"]["score"],
             "risk_max": s["risk"]["max"], "opportunity": s["opportunity"], "gaps": s["gaps"]} for s in scores.get("sites", [])]


def build(traffic=None, scan=None, access=None, scores=None, today: str | None = None) -> dict[str, list[dict]]:
    """Rows per table, in load order (bots before the hits that reference them)."""
    today = today or date.today().isoformat()
    tables: dict[str, list[dict]] = {}
    if traffic:
        tables["pagevet_bots"] = bot_rows(traffic)
        tables["pagevet_bot_hits"] = hit_rows(traffic)
    if scan:
        tables["pagevet_findings"] = finding_rows(scan)
    if access:
        tables["pagevet_crawler_access"] = access_rows(access, today)
    if scores:
        tables["pagevet_scores"] = score_rows(scores, today)
    return tables


def upsert(base_url: str, key: str, table: str, rows: list[dict], opener=urllib.request.urlopen) -> int:
    """POST rows to PostgREST with merge-duplicates; returns the number of rows sent."""
    if not base_url.startswith("https://"):
        raise ValueError("SUPABASE_URL must be an https:// URL")
    sent = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        req = urllib.request.Request(  # noqa: S310 - https only, checked above
            f"{base_url.rstrip('/')}/rest/v1/{table}?on_conflict={CONFLICT[table]}",
            data=json.dumps(chunk).encode(), method="POST",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"})
        with opener(req, timeout=60) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"{table}: HTTP {resp.status}")
        sent += len(chunk)
    return sent


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load PageVet reports into Supabase.")
    p.add_argument("--traffic")
    p.add_argument("--scan")
    p.add_argument("--access")
    p.add_argument("--scores")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    tables = build(_read(a.traffic), _read(a.scan), _read(a.access), _read(a.scores))
    if not tables:
        p.error("give at least one report")
    if a.dry_run:
        for table, rows in tables.items():
            sys.stdout.write(f"{table}: {len(rows)} rows" + (f"; first: {json.dumps(rows[0])[:200]}" if rows else "") + "\n")
        return 0
    url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and key):
        sys.stderr.write("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or use --dry-run)." + "\n")
        return 2
    for table, rows in tables.items():
        sys.stdout.write(f"{table}: {upsert(url, key, table, rows)} rows upserted" + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
