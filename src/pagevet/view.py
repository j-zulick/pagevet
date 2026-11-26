"""Human-vs-model view of one page.

    pagevet-view https://example.com/pricing --out view.html
    pagevet-view https://example.com/pricing --via firecrawl --out view.html   # rendered by your own Firecrawl
    pagevet-view page.html                                                     # a saved page

One self-contained HTML page with two columns: what a person sees (visible text and user-submitted text)
and what an AI model reading the raw page also gets (hidden elements, text hidden by stylesheet rules,
comments, attributes and meta tags, structured data, noscript). PageVet's findings are listed on top and
marked where they occur. With ``--via firecrawl`` the page is the HTML after scripts ran, so text a script
adds is on the left too. No script runs in the output; all page text is escaped.
"""

from __future__ import annotations

import argparse
import html
import sys
from collections.abc import Callable
from pathlib import Path

from pagevet import __version__
from pagevet.scan import _is_url, fetch_stylesheets, looks_like_html, read_source, scan_text, split_html

PERSON = (("visible text", "visible"), ("user-submitted content", "user_content"))
MODEL_ONLY = (("hidden elements", "hidden"), ("hidden by stylesheet rules", "hidden_by_css"), ("HTML comments", "comments"),
              ("attributes and meta tags", "attributes"), ("structured data (JSON-LD)", "structured"), ("noscript", "noscript"))
MAX_CHANNEL_CHARS = 30_000

_CSS = """body{font:15px/1.5 system-ui,sans-serif;margin:0;color:#1d1d1f;background:#fafafa}
header{padding:16px 24px;background:#fff;border-bottom:1px solid #ddd}h1{font-size:18px;margin:0 0 4px}
.meta{color:#555;font-size:13px}.findings{padding:12px 24px}.f{background:#fff;border-left:4px solid #999;margin:6px 0;padding:6px 10px}
.f.high{border-color:#b3261e}.f.medium{border-color:#c77700}.f.low{border-color:#6b6b6b}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 24px 24px}.col{background:#fff;border:1px solid #ddd;padding:12px}
h2{font-size:15px;margin:0 0 8px}h3{font-size:13px;margin:12px 0 4px;color:#444}p{margin:4px 0;white-space:pre-wrap;word-break:break-word}
mark{background:#ffe08a}.empty{color:#888;font-style:italic}@media(max-width:800px){.cols{grid-template-columns:1fr}}"""


def _mark(text: str, needles: list[str]) -> str:
    out = html.escape(text)
    for n in needles:
        e = html.escape(n)
        if e and e in out:
            out = out.replace(e, f"<mark>{e}</mark>")
    return out


def _section(title: str, chunks: list[str], needles: list[str]) -> str:
    body = "\n".join(chunks)
    if not body.strip():
        return f"<h3>{html.escape(title)}</h3><p class=empty>nothing</p>"
    note = ""
    if len(body) > MAX_CHANNEL_CHARS:
        body, note = body[:MAX_CHANNEL_CHARS], f" (first {MAX_CHANNEL_CHARS:,} characters)"
    paras = "".join(f"<p>{_mark(c, needles)}</p>" for c in body.split("\n") if c.strip())
    return f"<h3>{html.escape(title)}{note}</h3>{paras}"


def render_view(source: str, page_html: str, css: str = "", via: str = "http") -> str:
    """Return the view as a complete HTML document."""
    ch = split_html(page_html, css) if looks_like_html(page_html) else None
    result = scan_text(source, page_html, css=css)
    # Excerpts carry "…" at cut ends; mark the longest plain run of each.
    needles = [max(f.excerpt.strip("…").split("…"), key=len).strip() for f in result.findings]
    found = "".join(
        f'<div class="f {f.severity}"><b>{f.severity}</b> · {html.escape(f.channel)} · {html.escape(", ".join(f.kinds))}'
        f'{" · commercial" if f.intent else ""}<br>{html.escape(f.excerpt)}</div>'
        for f in result.findings
    ) or "<p class=empty>No findings. Pattern matching only: a clean result is not proof a page is safe.</p>"
    if ch is None:
        left = _section("text", [page_html], needles)
        right = "<p class=empty>Not an HTML page: there is no hidden text to separate.</p>"
    else:
        left = "".join(_section(t, getattr(ch, a), needles) for t, a in PERSON)
        right = "".join(_section(t, getattr(ch, a), needles) for t, a in MODEL_ONLY)
    how = "rendered by your Firecrawl (after scripts ran)" if via == "firecrawl" else "raw HTML (scripts not run)"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PageVet view: {html.escape(source)}</title>
<style>{_CSS}</style></head><body>
<header><h1>What a person sees, and what an AI model also reads</h1>
<div class=meta>{html.escape(source)} · {how} · PageVet {__version__} · {len(result.findings)} finding(s)</div></header>
<section class=findings>{found}</section>
<div class=cols><div class=col><h2>What a person sees</h2>{left}</div>
<div class=col><h2>What an AI model also reads</h2>{right}</div></div></body></html>
"""


def main(argv: list[str] | None = None, fetcher: Callable[[str], str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagevet-view", description="Show what a person sees next to what an AI model reads.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("source", help="an http(s) URL, a file path, or - for stdin")
    parser.add_argument("--via", choices=("http", "firecrawl"), default="http", help="how to read a URL (default: http)")
    parser.add_argument("--fetch-css", action="store_true", help="also apply the page's linked stylesheets on the same host")
    parser.add_argument("--out", metavar="FILE", help="write the HTML to FILE instead of stdout")
    args = parser.parse_args(argv)
    from pagevet.config import load_env_file

    load_env_file()
    if args.via == "firecrawl" and fetcher is None and _is_url(args.source):
        from pagevet import sources

        try:
            fetcher = sources.firecrawl_fetcher()
        except sources.SourceError as exc:
            parser.error(str(exc))
    try:
        body = read_source(args.source, fetcher)
        css = ""
        if args.fetch_css and _is_url(args.source):
            css, _ = fetch_stylesheets(body, args.source, fetcher)
    except Exception as exc:  # one page: report and stop
        sys.stderr.write(f"pagevet-view: {args.source}: {type(exc).__name__}: {exc}\n")
        return 2
    page = render_view(args.source, body, css, args.via)
    if args.out:
        Path(args.out).write_text(page, encoding="utf-8")
    else:
        sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
