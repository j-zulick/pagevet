# requirements:
# pagevet @ git+https://github.com/j-zulick/pagevet@main
"""Windmill script: re-scan pages on a schedule and alert on new findings.

Deploy (needs Windmill access): create a Python script from this file, give the worker access to
this repository for the requirement above, and attach a schedule (for example daily). The last
report is kept in the script's Windmill state, so each run reports only what changed. With
``raise_on_alert`` (default), a run with new findings at or above ``alert_on`` fails, which fires the
workspace's error handler (Slack, email); without it, branch on ``alert`` in a flow.
"""

from __future__ import annotations

try:  # Windmill provides this module; the fallback keeps the script runnable in tests
    import wmill
except ImportError:  # pragma: no cover
    wmill = None

from pagevet.rescan import rescan


def main(urls: list[str], alert_on: str = "medium", fetch_css: bool = False, raise_on_alert: bool = True,
         max_pages: int = 50) -> dict:
    previous = (wmill.get_state() if wmill else None) or []
    out = rescan(urls, previous=previous, alert_on=alert_on, fetch_css=fetch_css, max_pages=max_pages)
    if wmill:
        wmill.set_state(out["report"])
    summary = {"counts": out["counts"], "alert": out["alert"], "new": out["new"]}
    if out["alert"] and raise_on_alert:
        raise RuntimeError(f"PageVet: {out['counts']['new']} new finding(s) at or above {alert_on}: "
                           + "; ".join(f"{f['source']} [{f['severity']}] {f['channel']}" for f in out["new"][:10]))
    return summary
