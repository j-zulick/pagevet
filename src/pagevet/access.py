"""pagevet-access: which AI crawlers may read a page, and which actually can.

    pagevet-access https://example.com/pricing
    pagevet-access --urls urls.txt --format csv --out access.csv
    pagevet-access https://example.com/ --require search=allowed --require GPTBot=refused

For each of fourteen AI crawlers, grouped by what the operator uses the visits for (training,
search, fetching a page a person asked about), this reports:

- what the site's robots.txt says, parsed per RFC 9309 (groups by product token, longest match,
  ``allow`` wins a tie, ``*`` and ``$`` wildcards; a 4xx robots.txt allows everything, a 5xx or an
  unreachable one disallows everything);
- page-level signals: ``robots`` and per-crawler ``<meta>`` tags, ``X-Robots-Tag`` headers, the
  ``noai`` / ``noimageai`` values, and TDMRep (``tdm-reservation``) reservations;
- whether the site publishes ``/llms.txt`` (and ``/llms-full.txt``);
- with probes on (the default), what the server answers when the page is requested with each
  crawler's user agent, compared with a browser's. A crawler that robots.txt allows but the server
  refuses (401/402/403/429/451/503 or a challenge page) is a firewall refusal: robots.txt says yes,
  the site's firewall says no, often by accident.

``--require TARGET=STATE`` turns the report into a CI gate: TARGET is a crawler token or a group
(``training``, ``search``, ``fetch``, ``all``), STATE is ``allowed`` or ``refused``. Exit code 1 when
any requirement fails, 2 on a usage or fetch error, 0 otherwise.

Probes send one request per crawler per page; they impersonate the user-agent string only, not
the crawler's IP addresses, so a site that verifies crawlers by IP may answer differently to the
real crawler (docs/THREAT-MODEL.md). Tokens without a crawler of their own (Google-Extended,
Applebot-Extended) are robots.txt controls only and are not probed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit, urlunsplit

from pagevet import __version__

GROUPS = ("training", "search", "fetch")
GROUP_LABEL = {"training": "training", "search": "search", "fetch": "fetch on request"}


@dataclass(frozen=True)
class Crawler:
    token: str  # the robots.txt product token
    operator: str
    group: str
    user_agent: str = ""  # empty: robots.txt control token only, never visits on its own


CRAWLERS: tuple[Crawler, ...] = (
    Crawler("GPTBot", "OpenAI", "training", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot"),
    Crawler("ClaudeBot", "Anthropic", "training", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"),
    Crawler("Google-Extended", "Google", "training"),
    Crawler("Applebot-Extended", "Apple", "training"),
    Crawler("CCBot", "Common Crawl", "training", "CCBot/2.0 (https://commoncrawl.org/faq/)"),
    Crawler("meta-externalagent", "Meta", "training", "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    Crawler("Bytespider", "ByteDance", "training",
            "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)"),
    Crawler("Amazonbot", "Amazon", "training",
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot) Chrome/119.0 Safari/537.36"),
    Crawler("OAI-SearchBot", "OpenAI", "search", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot"),
    Crawler("Claude-SearchBot", "Anthropic", "search", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +https://www.anthropic.com)"),
    Crawler("PerplexityBot", "Perplexity", "search",
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    Crawler("ChatGPT-User", "OpenAI", "fetch", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    Crawler("Claude-User", "Anthropic", "fetch", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)"),
    Crawler("Perplexity-User", "Perplexity", "fetch",
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)"),
)
BY_TOKEN = {c.token.lower(): c for c in CRAWLERS}
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


# --- robots.txt, RFC 9309 ------------------------------------------------------------------------

ROBOTS_MAX_BYTES = 500 * 1024  # RFC 9309 2.5: parse at least the first 500 KiB


@dataclass
class RobotsGroup:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, path pattern)


def parse_robots(text: str) -> list[RobotsGroup]:
    """Parse robots.txt into groups (RFC 9309 2.1–2.2). Unknown lines (Sitemap, Crawl-delay) are skipped."""
    groups: list[RobotsGroup] = []
    current: RobotsGroup | None = None
    in_agents = False
    for raw in text.encode("utf-8", "replace")[:ROBOTS_MAX_BYTES].decode("utf-8", "replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not in_agents:
                current = RobotsGroup()
                groups.append(current)
                in_agents = True
            current.agents.append(value.lower())  # type: ignore[union-attr]
        elif key in ("allow", "disallow"):
            in_agents = False
            if current is not None and value:  # an empty Disallow allows everything
                current.rules.append((key == "allow", value))
        elif current is not None:
            in_agents = False
    return groups


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in _norm_path(body))
    return re.compile(rx + ("$" if anchored else ""))


def _norm_path(path: str) -> str:
    """Decode percent-escapes of unreserved characters so /a%62c and /abc compare equal (RFC 9309 2.2.2)."""
    return re.sub(r"%([0-9A-Fa-f]{2})", lambda m: unquote(m.group()) if unquote(m.group()).isalnum() or unquote(m.group()) in "-._~" else m.group().upper(), path)


def robots_verdict(groups: list[RobotsGroup], token: str, path: str) -> tuple[bool, str]:
    """Return (allowed, the rule that decided) for ``token`` and ``path`` (path plus query)."""
    if path.startswith("/robots.txt"):
        return True, "robots.txt itself is always allowed"
    token = token.lower()
    matched = [g for g in groups if token in g.agents]
    via = token
    if not matched:
        matched = [g for g in groups if "*" in g.agents]
        via = "*"
    rules = [r for g in matched for r in g.rules]
    if not rules:
        return True, "no rule" if not matched else f"no rule for {via}"
    best: tuple[int, bool, str] | None = None
    target = _norm_path(path)
    for allow, pattern in rules:
        if _pattern_regex(pattern).match(target):
            length = len(pattern)
            if best is None or length > best[0] or (length == best[0] and allow and not best[1]):
                best = (length, allow, pattern)
    if best is None:
        return True, f"no rule matches ({via})"
    return best[1], f"{'Allow' if best[1] else 'Disallow'}: {best[2]} ({via})"


# --- fetching -------------------------------------------------------------------------------------

@dataclass
class Response:
    status: int
    headers: dict[str, str]
    text: str
    error: str = ""


Getter = Callable[[str, str], Response]  # (url, user agent) -> Response
CHALLENGE = re.compile(
    r"cf-chl|challenge-platform|just a moment\.\.\.|attention required! \| cloudflare|captcha-delivery|px-captcha"
    r"|_incapsula_resource|access denied|request unsuccessful|verify you are (?:a )?human|are you a robot",
    re.I,
)
REFUSAL_STATUS = {401, 402, 403, 429, 451, 503}


def http_get(timeout: float = 15.0, allow_private: bool = True, max_bytes: int = 2_000_000) -> Getter:
    """A getter over httpx, following redirects, reading at most ``max_bytes``."""
    import httpx

    from pagevet.scan import _refuse_private

    hooks = {} if allow_private else {"request": [_refuse_private]}

    def get(url: str, user_agent: str) -> Response:
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": user_agent}, event_hooks=hooks) as client, \
                    client.stream("GET", url) as r:
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) >= max_bytes:
                        break
                return Response(r.status_code, {k.lower(): v for k, v in r.headers.items()}, body.decode(r.encoding or "utf-8", "replace"))
        except Exception as exc:  # report, don't raise: one site failing must not stop the run
            return Response(0, {}, "", f"{type(exc).__name__}: {exc}"[:200])

    return get


# --- page signals ---------------------------------------------------------------------------------

class _Meta(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            if a.get("name"):
                self.meta.append((a["name"].strip().lower(), a.get("content", "").strip().lower()))


def page_signals(html: str, headers: dict[str, str]) -> dict[str, list[str]]:
    """Return directives per target ("*" or a crawler token) from meta tags and X-Robots-Tag headers."""
    out: dict[str, list[str]] = {}

    def add(target: str, content: str) -> None:
        for d in re.split(r"\s*,\s*", content):
            if d and d not in out.setdefault(target, []):
                out[target].append(d)

    parser = _Meta()
    try:
        parser.feed(html[:2_000_000])
    except Exception:  # noqa: S110 - malformed markup: keep the meta tags read so far
        pass
    for name, content in parser.meta:
        if name == "robots":
            add("*", content)
        elif name in BY_TOKEN:
            add(BY_TOKEN[name].token, content)
        elif name == "tdm-reservation" and content.strip() == "1":
            add("*", "tdm-reservation")
    for value in re.split(r",(?=\s*[\w-]+\s*:)|\n", headers.get("x-robots-tag", "")):
        value = value.strip().lower()
        if not value:
            continue
        m = re.match(r"([\w-]+)\s*:\s*(.+)", value)
        if m and m.group(1) in BY_TOKEN:
            add(BY_TOKEN[m.group(1)].token, m.group(2))
        else:
            add("*", value)
    if headers.get("tdm-reservation", "").strip() == "1":
        add("*", "tdm-reservation")
    return out


# --- the report -----------------------------------------------------------------------------------

@dataclass
class CrawlerAccess:
    token: str
    operator: str
    group: str
    robots: str  # allowed | disallowed | unreachable
    robots_rule: str
    page_signals: list[str]
    probe: str  # served | refused (status) | challenge | error | not probed
    status: int | None
    verdict: str  # allowed | refused by robots.txt | refused by server | allowed (unverified)
    note: str = ""


@dataclass
class AccessReport:
    url: str
    robots_txt: str  # found | missing (4xx) | unreachable (5xx/error)
    llms_txt: dict
    browser_status: int | None
    crawlers: list[CrawlerAccess]
    error: str = ""

    def refused(self, token: str) -> bool:
        return next(c for c in self.crawlers if c.token == token).verdict.startswith("refused")

    def summary(self) -> dict[str, str]:
        out = {}
        for g in GROUPS:
            members = [c for c in self.crawlers if c.group == g]
            n = sum(not c.verdict.startswith("refused") for c in members)
            out[g] = f"{n} of {len(members)} allowed"
        return out


def _root(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, "", "", ""))


def _path(url: str) -> str:
    p = urlsplit(url)
    return (p.path or "/") + (f"?{p.query}" if p.query else "")


def llms_txt(root: str, get: Getter) -> dict:
    out: dict = {}
    for name in ("llms.txt", "llms-full.txt"):
        r = get(f"{root}/{name}", BROWSER_UA)
        body = r.text.lstrip("﻿")
        ctype = r.headers.get("content-type", "")
        present = r.status == 200 and "html" not in ctype and not body.lstrip().lower().startswith(("<!doctype", "<html"))
        entry: dict = {"present": present, "status": r.status or None}
        if present:
            first = next((ln for ln in body.splitlines() if ln.strip()), "")
            entry.update(title=first[2:].strip() if first.startswith("# ") else "", links=len(re.findall(r"\]\((https?://|/)[^)]+\)", body)),
                         bytes=len(body.encode()), follows_format=first.startswith("# "))
        out[name] = entry
    return out


def check(url: str, get: Getter | None = None, probe: bool = True, tokens: list[str] | None = None) -> AccessReport:
    """Build the access report for one page."""
    get = get or http_get()
    root = _root(url)
    rr = get(f"{root}/robots.txt", BROWSER_UA)
    if rr.error or rr.status >= 500 or rr.status == 0:
        robots_state, groups = "unreachable", None
    elif 400 <= rr.status < 500:
        robots_state, groups = "missing", []
    else:
        robots_state, groups = "found", parse_robots(rr.text)
    page = get(url, BROWSER_UA)
    signals = page_signals(page.text, page.headers) if not page.error else {}
    chosen = [c for c in CRAWLERS if not tokens or c.token.lower() in {t.lower() for t in tokens}]
    rows = []
    for c in chosen:
        if groups is None:
            allowed, rule, state = False, "robots.txt unreachable: RFC 9309 treats the site as fully disallowed", "unreachable"
        else:
            allowed, rule = robots_verdict(groups, c.token, _path(url))
            state = "allowed" if allowed else "disallowed"
            if robots_state == "missing":
                rule = f"robots.txt answered {rr.status}: everything allowed"
        sig = signals.get("*", []) + signals.get(c.token, [])
        status, probe_state = None, "not probed"
        if probe and c.user_agent and allowed:
            r = get(url, c.user_agent)
            status = r.status or None
            if r.error:
                probe_state = "error"
            elif r.status in REFUSAL_STATUS:
                probe_state = f"refused ({r.status})"
            elif CHALLENGE.search(r.text[:20000]) and not CHALLENGE.search(page.text[:20000]):
                probe_state = "challenge page"
            else:
                probe_state = "served"
        if not allowed:
            verdict = "refused by robots.txt"
        elif probe_state.startswith(("refused", "challenge")):
            verdict = "refused by server"
        elif probe_state == "served":
            verdict = "allowed"
        else:
            verdict = "allowed (unverified)"
        note = ""
        if verdict == "refused by server":
            note = "robots.txt allows this crawler but the server refused it: a firewall or bot-management rule, often unintended"
        elif "noai" in sig or "tdm-reservation" in sig:
            note = "allowed to fetch, but the page asks not to be used for AI (noai or TDM reservation)"
        elif "noindex" in sig or "none" in sig:
            note = "allowed to fetch, but the page asks not to be indexed"
        rows.append(CrawlerAccess(c.token, c.operator, c.group, state, rule, sig, probe_state, status, verdict, note))
    error = page.error or (f"page answered {page.status}" if page.status >= 400 else "")
    return AccessReport(url, robots_state, llms_txt(root, get), page.status or None, rows, error)


# --- requirements ---------------------------------------------------------------------------------

def parse_requirement(text: str) -> tuple[str, str]:
    target, _, state = text.partition("=")
    target, state = target.strip(), state.strip().lower()
    if state not in ("allowed", "refused") or not target:
        raise ValueError(f"--require {text!r}: use TARGET=allowed or TARGET=refused")
    if target.lower() not in (*GROUPS, "all") and target.lower() not in BY_TOKEN:
        raise ValueError(f"--require {text!r}: unknown crawler or group {target!r}")
    return target, state


def failed_requirements(report: AccessReport, requirements: list[tuple[str, str]]) -> list[str]:
    out = []
    for target, state in requirements:
        t = target.lower()
        members = [c for c in report.crawlers if t == "all" or c.group == t or c.token.lower() == t]
        for c in members:
            refused = c.verdict.startswith("refused")
            if (state == "refused") != refused:
                out.append(f"{report.url}: {c.token} is {c.verdict}, required {state}")
    return out


# --- rendering ------------------------------------------------------------------------------------

def render_text(reports: list[AccessReport]) -> str:
    lines = []
    for r in reports:
        lines.append(f"{r.url}")
        if r.error:
            lines.append(f"  page: {r.error}")
        lines.append(f"  robots.txt: {r.robots_txt}; llms.txt: {'yes' if r.llms_txt.get('llms.txt', {}).get('present') else 'no'}")
        lines.append("  " + "; ".join(f"{GROUP_LABEL[g]}: {v}" for g, v in r.summary().items()))
        for c in r.crawlers:
            extra = f" [{', '.join(c.page_signals)}]" if c.page_signals else ""
            lines.append(f"  {c.token:<19} {GROUP_LABEL[c.group]:<17} {c.verdict:<22} {c.probe:<15} {c.robots_rule}{extra}")
            if c.note:
                lines.append(f"  {'':<19} {c.note}")
        lines.append("")
    lines.append("Probes send each crawler's user-agent string, not its IP addresses; a site that checks IPs may answer the real crawler differently.")
    return "\n".join(lines) + "\n"


def render_json(reports: list[AccessReport]) -> str:
    return json.dumps({"tool": "pagevet-access", "version": __version__,
                       "reports": [{**asdict(r), "summary": r.summary()} for r in reports]}, indent=1) + "\n"


def render_csv(reports: list[AccessReport]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["url", "crawler", "operator", "group", "verdict", "robots", "robots_rule", "probe", "status", "page_signals", "llms_txt", "note"])
    for r in reports:
        llms = "yes" if r.llms_txt.get("llms.txt", {}).get("present") else "no"
        for c in r.crawlers:
            w.writerow([r.url, c.token, c.operator, c.group, c.verdict, c.robots, c.robots_rule, c.probe, c.status or "", " ".join(c.page_signals), llms, c.note])
    return buf.getvalue()


def render_markdown(reports: list[AccessReport]) -> str:
    out = ["# AI crawler access", ""]
    for r in reports:
        out += [f"## {r.url}", "", f"robots.txt {r.robots_txt}; llms.txt {'present' if r.llms_txt.get('llms.txt', {}).get('present') else 'absent'}. "
                + "; ".join(f"{GROUP_LABEL[g]}: {v}" for g, v in r.summary().items()) + ".", "",
                "| Crawler | Operator | Use | Verdict | Probe | robots.txt rule | Page signals |", "|---|---|---|---|---|---|---|"]
        for c in r.crawlers:
            out.append(f"| {c.token} | {c.operator} | {GROUP_LABEL[c.group]} | {c.verdict} | {c.probe} | {c.robots_rule.replace('|', '/')} | {' '.join(c.page_signals)} |")
        notes = [f"- {c.token}: {c.note}" for c in r.crawlers if c.note]
        out += ["", *notes, ""] if notes else [""]
    out.append("Probes send each crawler's user-agent string, not its IP addresses.")
    return "\n".join(out) + "\n"


RENDERERS = {"text": render_text, "json": render_json, "csv": render_csv, "markdown": render_markdown}


def main(argv: list[str] | None = None, get: Getter | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagevet-access", description="Which AI crawlers may read a page, and which actually can.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("urls", nargs="*", help="http(s) page URLs")
    parser.add_argument("--urls", dest="url_file", metavar="FILE", help="file with one URL per line")
    parser.add_argument("--format", choices=sorted(RENDERERS), default="text")
    parser.add_argument("--out", metavar="FILE", help="write the report to FILE")
    parser.add_argument("--no-probe", action="store_true", help="read robots.txt and page signals only; don't request the page as each crawler")
    parser.add_argument("--crawler", action="append", default=[], metavar="TOKEN", help=f"only these crawlers (default: all {len(CRAWLERS)})")
    parser.add_argument("--require", action="append", default=[], metavar="TARGET=STATE",
                        help="fail (exit 1) unless TARGET (crawler token, training, search, fetch or all) is allowed or refused")
    parser.add_argument("--timeout", type=float, default=15.0, metavar="SECONDS")
    args = parser.parse_args(argv)
    urls = list(args.urls)
    if args.url_file:
        with open(args.url_file) as fh:
            urls += [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    if not urls:
        parser.print_help()
        return 2
    try:
        requirements = [parse_requirement(r) for r in args.require]
        unknown = [t for t in args.crawler if t.lower() not in BY_TOKEN]
        if unknown:
            raise ValueError(f"unknown crawler {unknown[0]!r}; known: {', '.join(c.token for c in CRAWLERS)}")
    except ValueError as exc:
        sys.stderr.write(f"pagevet-access: {exc}\n")
        return 2
    getter = get or http_get(args.timeout)
    reports = []
    for u in urls:
        if not re.match(r"https?://", u):
            reports.append(AccessReport(u, "unreachable", {}, None, [], "not an http(s) URL"))
            continue
        reports.append(check(u, getter, probe=not args.no_probe, tokens=args.crawler or None))
    text = RENDERERS[args.format](reports)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    failures = [f for r in reports for f in failed_requirements(r, requirements)]
    for f in failures:
        sys.stderr.write(f"requirement failed: {f}\n")
    if failures:
        return 1
    return 2 if any(r.error and not r.crawlers for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
