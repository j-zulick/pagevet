"""A guard between fetching a page and handing it to a model.

    from pagevet.guard import guard
    result = guard(url, html)              # GuardResult(allowed, text, findings, removed)
    if result.allowed: prompt = result.text

    pagevet-guard https://example.com/page               # cleaned text on stdout; exit 1 when blocked
    curl -s https://example.com/page | pagevet-guard - --json

What the model gets is the text a person sees (visible and user-submitted text) and nothing a person can't
see: hidden elements, stylesheet-hidden text, comments, attributes, structured data and noscript are dropped
and counted. Any paragraph that still matches an instruction pattern is replaced by a short marker, and chat
markup or tags that could close a data wrapper are removed. ``policy`` decides when the page is blocked
outright: ``high`` (default) blocks a page with a high finding, ``medium`` blocks at medium or high, ``never``
only cleans. Detection only: the guard removes text, it never writes any.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from pagevet import __version__
from pagevet.detect import INSTRUCTION_PATTERNS, neutralize, scan
from pagevet.scan import SEVERITIES, Finding, looks_like_html, read_source, scan_text, split_html

POLICIES = ("high", "medium", "never")
MODEL_ONLY = ("hidden", "hidden_by_css", "comments", "attributes", "structured", "noscript")


@dataclass
class GuardResult:
    allowed: bool
    text: str
    findings: list[Finding] = field(default_factory=list)
    removed: dict[str, int] = field(default_factory=dict)  # channel -> chunks dropped; "instructions" -> paragraphs replaced


def _clean(chunks: list[str], removed: dict[str, int]) -> list[str]:
    out = []
    for chunk in chunks:
        kinds = sorted({h.kind.split(":")[-1] for h in scan(chunk)} & set(INSTRUCTION_PATTERNS))
        if kinds:
            removed["instructions"] = removed.get("instructions", 0) + 1
            out.append(f"[text aimed at AI removed by PageVet: {', '.join(kinds)}]")
        else:
            out.append(neutralize(chunk))
    return out


def guard(source: str, content: str, policy: str = "high") -> GuardResult:
    """Clean one page for a model and decide whether to pass it at all."""
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {', '.join(POLICIES)}")
    findings = scan_text(source, content).findings
    removed: dict[str, int] = {}
    if looks_like_html(content):
        ch = split_html(content)
        for name in MODEL_ONLY:
            if getattr(ch, name):
                removed[name] = len(getattr(ch, name))
        kept = _clean(ch.visible + ch.user_content, removed)
    else:
        kept = _clean([p for p in content.split("\n") if p.strip()], removed)
    floor = None if policy == "never" else SEVERITIES.index(policy)
    blocked = floor is not None and any(SEVERITIES.index(f.severity) >= floor for f in findings)
    return GuardResult(not blocked, "\n".join(kept), findings, removed)


def main(argv: list[str] | None = None, fetcher: Callable[[str], str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagevet-guard", description="Clean a page before a model reads it.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("source", help="an http(s) URL, a file path, or - for stdin")
    parser.add_argument("--policy", choices=POLICIES, default="high", help="block a page at this severity (default: high)")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args(argv)
    try:
        body = read_source(args.source, fetcher)
    except Exception as exc:  # one page: report and stop
        sys.stderr.write(f"pagevet-guard: {args.source}: {type(exc).__name__}: {exc}\n")
        return 2
    result = guard(args.source, body, args.policy)
    if args.json:
        sys.stdout.write(json.dumps(asdict(result), indent=2, ensure_ascii=False) + "\n")
    elif result.allowed:
        sys.stdout.write(result.text + "\n")
    else:
        sys.stderr.write(f"pagevet-guard: blocked {args.source}: {len(result.findings)} finding(s), policy {args.policy}\n")
    return 0 if result.allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
