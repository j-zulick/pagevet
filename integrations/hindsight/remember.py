"""Give an agent memory of what PageVet measured, with Hindsight (agent memory: retain, recall, reflect).

    python integrations/hindsight/remember.py --scores scores.json --traffic traffic.json --dry-run
    HINDSIGHT_URL=http://localhost:8888 python integrations/hindsight/remember.py --scores scores.json --traffic traffic.json --bank my-site
    HINDSIGHT_URL=... python integrations/hindsight/remember.py --bank my-site --ask "Why did AI-crawler hits change on /pricing?"

Supabase keeps the numbers (integrations/supabase/). Hindsight keeps short, dated observations an agent can recall
and reflect on later ("ClaudeBot hits on /pricing rose after the 2026-10-20 update"). Observations are written from
the reports with fixed templates, no model, so they say only what the reports show. Needs `pip install
hindsight-client` and a Hindsight server (self-hosted or Hindsight Cloud); HINDSIGHT_API_KEY only for the cloud.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def observations(scores: dict | None = None, traffic: dict | None = None, date: str = "") -> list[dict]:
    """Short, dated facts from PageVet reports, each with the context Hindsight stores alongside it."""
    out = []
    for s in (scores or {}).get("sites", []):
        v = s["visibility"]["score"]
        out.append({"content": f"PageVet scored {s['site']}: AI visibility {v if v is not None else 'not measured'}/100, "
                               f"worst page risk {s['risk']['max']}/100, opportunity {s['opportunity']}/100 (score version {scores['score_version']}).",
                    "context": "pagevet scores"})
        for g in s.get("gaps", []):
            out.append({"content": f"{s['site']}: {g['kind']}: {g['detail']}.", "context": "pagevet gap"})
    if traffic:
        period = traffic.get("period") or {}
        for b in traffic.get("by_bot", []):
            out.append({"content": f"{b['bot']} ({b.get('group', '')}) made {b['hits']} requests between {period.get('first')} and {period.get('last')}.",
                        "context": "bot traffic"})
        for w in traffic.get("updates", []) or []:
            days = w.get("window_days", 14)
            out.append({"content": f"Around the {w['date']} update of {w['url']}: {w['ai_hits_before']} AI-crawler hits in the {days} days before, "
                                   f"{w['ai_hits_after']} in the {days} days after (a signal, not proof).", "context": "content update"})
            for bot, n in sorted((w.get("by_bot") or {}).items()):
                out.append({"content": f"{bot} on {w['url']}: {n['before']} hits in the {days} days before the {w['date']} update, {n['after']} after.",
                            "context": "content update"})
    for o in out:
        if date:
            o["timestamp"] = date
    return out


def client():
    try:
        from hindsight_client import Hindsight
    except ImportError:
        sys.exit("pip install hindsight-client")
    url = os.environ.get("HINDSIGHT_URL", "")
    if not url:
        sys.exit("Set HINDSIGHT_URL (and HINDSIGHT_API_KEY for Hindsight Cloud), or use --dry-run.")
    key = os.environ.get("HINDSIGHT_API_KEY") or None
    return Hindsight(base_url=url, api_key=key) if key else Hindsight(base_url=url)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Retain PageVet observations in a Hindsight memory bank, or ask it.")
    p.add_argument("--scores")
    p.add_argument("--traffic")
    p.add_argument("--bank", default=os.environ.get("HINDSIGHT_BANK", "pagevet"))
    p.add_argument("--date", default="", help="ISO date to stamp the observations with")
    p.add_argument("--ask", help="recall and reflect on this question instead of retaining")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if a.ask:
        c = client()
        for r in c.recall(bank_id=a.bank, query=a.ask).results[:10]:
            sys.stdout.write(f"- {r.text}\n")
        sys.stdout.write("\n" + c.reflect(bank_id=a.bank, query=a.ask).text + "\n")
        return 0
    items = observations(json.loads(Path(a.scores).read_text()) if a.scores else None,
                         json.loads(Path(a.traffic).read_text()) if a.traffic else None, a.date)
    if not items:
        p.error("give --scores and/or --traffic")
    if a.dry_run:
        for o in items:
            sys.stdout.write(f"[{o['context']}] {o['content']}" + "\n")
        return 0
    c = client()
    c.retain_batch(bank_id=a.bank, items=items)
    sys.stdout.write(f"retained {len(items)} observations in bank {a.bank!r}" + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
