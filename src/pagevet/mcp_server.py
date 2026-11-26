"""PageVet as an MCP server, so an assistant (Claude, ChatGPT, Cursor) can scan a page.

    pip install "pagevet[mcp]"
    pagevet-mcp            # stdio transport

Two tools. ``scan_page``: give it a public http(s) URL or pasted HTML/text. URLs that resolve to
loopback, private, link-local or reserved addresses are refused (checked on every redirect),
because the caller here is a model and may have been handed the URL by a page it read. With
``fetch_css``, the page's own linked stylesheets (same host) are read under the same rule.
``check_ai_access``: which AI crawlers may read a page, and which the server actually serves.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from pagevet.scan import (
    DISCLAIMER,
    MAX_STYLESHEET_BYTES,
    Robots,
    fetch,
    fetch_bytes,
    fetch_stylesheets,
    is_pdf_source,
    looks_like_html,
    scan_pdf,
    scan_text,
)

MAX_TEXT = 2_000_000


def scan_page(url: str = "", html: str = "", include_repetition: bool = False,
              fetcher: Callable[[str], str] | None = None, fetch_css: bool = False,
              css_fetcher: Callable[[str], str] | None = None, ignore_robots: bool = False,
              robots_fetcher: Callable[[str], str] | None = None,
              pdf_fetcher: Callable[[str], bytes] | None = None, css_any_host: bool = False) -> dict:
    """Scan one page for text aimed at AI models; return findings with severity and advice.

    ``fetch_css`` (URL only) also reads the page's own linked stylesheets for hiding rules, with
    non-public addresses refused as for the page itself. A URL that robots.txt disallows for pagevet
    is not fetched unless ``ignore_robots`` is set.
    """
    if bool(url) == bool(html):
        return {"error": "give exactly one of url or html"}
    if html and len(html) > MAX_TEXT:
        return {"error": f"html is too long (limit {MAX_TEXT:,} characters)"}
    if url and not ignore_robots and (robots_fetcher or fetcher is None):
        robots = Robots(robots_fetcher or (lambda u: fetch(u, timeout=10.0, allow_private=False, max_bytes=500_000)))
        if not robots.allowed(url):
            return {"error": "robots.txt disallows this page for pagevet; set ignore_robots for your own site"}
    if url and is_pdf_source(url):
        try:
            data = (pdf_fetcher or (lambda u: fetch_bytes(u, allow_private=False)))(url)
            result = asdict(scan_pdf(url, data, include_repetition))
        except Exception as exc:  # report problems to the caller instead of raising
            return {"error": f"{type(exc).__name__}: {exc}"[:300]}
        result["note"] = DISCLAIMER
        return result
    try:
        body = html or (fetcher or (lambda u: fetch(u, timeout=20.0, allow_private=False, max_bytes=5_000_000)))(url)
    except Exception as exc:  # report fetch problems to the caller instead of raising
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
    css, notes = "", []
    if fetch_css and url and looks_like_html(body):
        css, notes = fetch_stylesheets(body, url, css_fetcher or (
            lambda u: fetch(u, timeout=10.0, allow_private=False, max_bytes=MAX_STYLESHEET_BYTES)), any_host=css_any_host)
    result = asdict(scan_text(url or "pasted", body, include_repetition, css))
    result["note"] = DISCLAIMER
    if notes:
        result["stylesheet_notes"] = notes
    return result


def check_ai_access(url: str, probe: bool = True, get: Callable | None = None) -> dict:
    """Which of fourteen AI crawlers may read ``url`` (robots.txt per RFC 9309, page signals,
    llms.txt) and, with ``probe``, which the server actually serves. Non-public addresses are refused."""
    from dataclasses import asdict as _asdict

    from pagevet.access import check, http_get

    if not url.startswith(("http://", "https://")):
        return {"error": "give an http(s) URL"}
    report = check(url, get or http_get(timeout=15.0, allow_private=False), probe=probe)
    if report.error and "non-public" in report.error.lower():
        return {"error": report.error}
    out = _asdict(report)
    out["summary"] = report.summary()
    out["note"] = "Probes send each crawler's user-agent string, not its IP addresses."
    return out


def main(argv: list[str] | None = None) -> None:
    """Serve ``scan_page`` over stdio."""
    import argparse

    from pagevet import __version__, install_hint
    from pagevet.config import load_env_file

    parser = argparse.ArgumentParser(
        prog="pagevet-mcp", description="Serve PageVet's scan_page and check_ai_access tools over stdio for MCP clients (Claude, Codex, Cursor).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    load_env_file()
    try:
        from mcp.server.mcpserver import MCPServer  # MCP Python SDK 2.x
    except ImportError as exc:
        raise SystemExit(f"pagevet-mcp needs the optional extra: {install_hint('mcp')}") from exc

    server = MCPServer("pagevet", version=__version__)

    @server.tool(name="scan_page")
    def scan_page_tool(url: str = "", html: str = "", include_repetition: bool = False, fetch_css: bool = False,
                       css_any_host: bool = False, ignore_robots: bool = False) -> dict:
        """Check a public web page (url) or pasted HTML (html) for text aimed at AI models (prompt injection).

        Returns findings per channel (visible text, hidden elements, HTML comments, attributes and meta
        tags, structured data, noscript; for a .pdf URL, its page text and its metadata and annotations) with severity (high/medium/low), the pattern kinds and advice.
        Set fetch_css to also apply the page's own linked stylesheets when deciding what is hidden, and
        css_any_host to include stylesheets on other hosts (CDNs).
        Pages that robots.txt disallows for pagevet are not fetched unless ignore_robots is set.
        Non-public addresses are refused. Pattern matching only: no findings is not proof of safety.
        """
        return scan_page(url, html, include_repetition, fetch_css=fetch_css, css_any_host=css_any_host,
                         ignore_robots=ignore_robots)

    @server.tool(name="check_ai_access")
    def check_ai_access_tool(url: str, probe: bool = True) -> dict:
        """Report which AI crawlers (training, search, fetch on request; 14 in all) may read a public page:
        robots.txt per RFC 9309, robots meta tags, X-Robots-Tag, noai and TDM reservations, llms.txt, and with
        probe, what the server answers each crawler's user agent (firewall refusals). Non-public addresses are refused.
        """
        return check_ai_access(url, probe)

    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
