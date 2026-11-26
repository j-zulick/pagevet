"""Where pages come from: plain HTTP, a Firecrawl service, or a crawlee-server crawl.

    pagevet --via firecrawl https://example.com/      # rendered HTML, gets past simple bot blocks
    pagevet --crawl https://example.com/ --max-pages 25

Plain HTTP is the default and needs nothing. The other two use services you run yourself, set by
environment variables (never command-line arguments, so tokens stay out of shell history):

    PAGEVET_FIRECRAWL_URL, PAGEVET_FIRECRAWL_KEY     a Firecrawl instance (API v1: POST /v1/scrape)
    PAGEVET_CRAWL_URL, PAGEVET_CRAWL_TOKEN           a crawlee-server instance (POST /v1/crawl)

A crawl asks crawlee-server to capture each page, then reads the stored raw body, so every scanned
page carries the capture id, SHA-256 and fetch time that crawlee-server recorded for it.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field

Post = Callable[[str, dict, dict], dict]   # (url, headers, json body) -> parsed JSON
Get = Callable[[str, dict], str]           # (url, headers) -> body text


class SourceError(RuntimeError):
    """A page source is not configured or answered with an error."""


def _post(url: str, headers: dict, body: dict, timeout: float = 120.0) -> dict:
    import httpx

    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    if resp.status_code >= 400:
        raise SourceError(f"{url.split('?')[0]} answered HTTP {resp.status_code}")
    return resp.json()


def _get(url: str, headers: dict, timeout: float = 60.0) -> str:
    import httpx

    resp = httpx.get(url, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise SourceError(f"{url.split('?')[0]} answered HTTP {resp.status_code}")
    return resp.text


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SourceError(f"{name} is not set")
    return value.rstrip("/") if name.endswith("_URL") else value


def _http_url(url: str) -> str:
    if not re.match(r"https?://", url, re.I):
        raise ValueError("only http(s) URLs are fetched")
    return url


def firecrawl_fetcher(post: Post = _post) -> Callable[[str], str]:
    """Return a fetcher that reads a page's rendered HTML through Firecrawl (``rawHtml``)."""
    base, key = _env("PAGEVET_FIRECRAWL_URL"), os.environ.get("PAGEVET_FIRECRAWL_KEY", "").strip()
    headers = {"authorization": f"Bearer {key}"} if key else {}

    def fetch(url: str) -> str:
        out = post(f"{base}/v1/scrape", headers, {"url": _http_url(url), "formats": ["rawHtml"]})
        html = (out.get("data") or {}).get("rawHtml")
        if not out.get("success", True) or not isinstance(html, str):
            raise SourceError("Firecrawl returned no rawHtml for this page")
        return html

    return fetch


@dataclass
class CrawledPage:
    """One page from a crawl, with the evidence crawlee-server recorded for it."""

    url: str
    body: str
    evidence: dict = field(default_factory=dict)


CRAWL_MODES = ("crawl", "page", "sitemap", "map")


def _host(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).hostname or ""


def crawl(start_url: str | list[str], max_pages: int = 25, post: Post = _post, get: Get = _get,
          mode: str = "crawl", report: dict | None = None) -> tuple[list[CrawledPage], list[str]]:
    """Crawl through crawlee-server with page capture on; return (pages, notes).

    ``start_url`` is one URL or up to 10. ``mode`` is crawlee-server's: ``crawl`` follows links,
    ``page`` fetches only the start URLs, ``sitemap`` reads /sitemap.xml, ``map`` uses Firecrawl's
    site map. Only pages crawlee-server stored a capture for are returned; the notes say how many
    it reported without one, which start URLs gave no page, and its status when partial. If
    ``report`` is a dict, crawlee-server's ``failures`` and ``refused`` lists are copied into it.
    """
    starts = [start_url] if isinstance(start_url, str) else list(start_url)
    if not 1 <= len(starts) <= 10:
        raise ValueError("crawlee-server takes 1 to 10 start URLs")
    if mode not in CRAWL_MODES:
        raise ValueError(f"mode must be one of {', '.join(CRAWL_MODES)}")
    base, token = _env("PAGEVET_CRAWL_URL"), _env("PAGEVET_CRAWL_TOKEN")
    headers = {"authorization": f"Bearer {token}"}
    body = {"start_urls": [_http_url(u) for u in starts], "max_pages": max_pages, "capture": True, "mode": mode}
    out = post(f"{base}/v1/crawl", headers, body)
    if report is not None:
        report["failures"] = list(out.get("failures") or [])
        report["refused"] = list(out.get("refused") or [])
    pages: list[CrawledPage] = []
    missing = 0
    for rec in out.get("records") or []:
        cid = rec.get("capture_id")
        if not (isinstance(cid, str) and re.fullmatch(r"[0-9a-f]{48}", cid)):
            missing += 1
            continue
        url = rec.get("listing_url") or rec.get("url") or starts[0]
        evidence = {k: rec[k] for k in ("capture_id", "sha256", "fetched_at", "fetched_via") if rec.get(k)}
        pages.append(CrawledPage(url, get(f"{base}/v1/captures/{cid}", headers), evidence))
    notes = []
    if out.get("status") not in (None, "ok", "complete", "completed"):
        notes.append(f"crawl status: {out.get('status')}")
    if missing:
        notes.append(f"{missing} record(s) had no stored capture and were not scanned")
    if mode == "page":
        got = {_host(p.url) for p in pages}  # a start URL may come back under its redirect target
        unread = [u for u in starts if _host(u) not in got]
        if unread:
            notes.append(f"no page returned for: {', '.join(unread)}")
    return pages, notes
