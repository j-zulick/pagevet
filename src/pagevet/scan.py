"""pagevet: check web pages for text aimed at AI models.

    pagevet page.html https://example.com/pricing
    pagevet --sitemap https://example.com/sitemap.xml --format html --out audit.html
    pagevet --compare-agents https://example.com/
    pagevet --format sarif --fail-on high --urls urls.txt > pagevet.sarif
    pagevet --urls urls.txt --baseline last.json --format json --out now.json

A page can carry instructions written for the AI that reads it rather than for a person. This
command splits each page into what a reader sees and the channels a reader doesn't (hidden
elements, HTML comments, attributes and meta tags, structured data, noscript), runs the
deterministic checks in ``pagevet.detect`` on each, rates every finding (high, medium, low) with
advice, and reports as text, JSON, CSV, HTML or SARIF.

With ``--baseline`` (an earlier JSON report), only findings not in that report are kept, so the
exit code and the report cover what is new since then.

Exit code: 0 when nothing at or above ``--fail-on`` was found, 1 when something was, 2 on a usage
or fetch error with no findings. Pattern matching only: a clean result means none of the patterns
matched, not that the page is safe.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from defusedxml.ElementTree import fromstring as safe_fromstring

from pagevet import __version__, install_hint
from pagevet.detect import HIDDEN_PATTERNS, INSTRUCTION_PATTERNS, commercial, scan
from pagevet.detectors import build as build_detector

Fetcher = Callable[[str], str]
MAX_SITEMAP_BYTES = 5_000_000
MAX_CHILD_SITEMAPS = 50

HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?![.\d])|opacity\s*:\s*0(?![.\d]*[1-9])"
    r"|opacity\s*:\s*0?\.0\d*(?![\d])"  # below 0.1: nearly invisible
    r"|font-size\s*:\s*(?:0?\.\d+|1)px|font-size\s*:\s*0?\.[0-2]\d*r?em"  # 1px, 0.5px, 0.1em
    r"|(?<![\w-])(?:left|top|right|bottom|text-indent)\s*:\s*-(?:\d{3,}px|\d{2,}(?:\.\d+)?r?em)"  # off-screen
    r"|clip\s*:\s*rect\(\s*0|clip-path\s*:\s*(?:inset\(\s*(?:50|100)%|circle\(\s*0)"
    r"|transform\s*:\s*scale\(\s*0(?:\.0*)?\s*[,)]"
    r"|(?<![\w-])(?:max-)?(?:height|width)\s*:\s*0(?:px)?\s*;[^\"']*overflow\s*:\s*hidden"
    r"|overflow\s*:\s*hidden\s*;[^\"']*(?<![\w-])(?:max-)?(?:height|width)\s*:\s*0(?![.\d])",
    re.I,
)
TRANSPARENT = re.compile(r"(?<![\w-])color\s*:\s*transparent", re.I)
CLIP_TEXT = re.compile(r"background-clip\s*:\s*text", re.I)


def hides(style: str) -> bool:
    """Whether a CSS declaration block hides its element's text from a person.

    ``color: transparent`` counts unless the same block clips a background to the text (the usual
    gradient-text effect, which is visible). ``min-width``/``min-height`` and ``line-height`` of 0
    do not count.
    """
    if HIDDEN_STYLE.search(style):
        return True
    return bool(TRANSPARENT.search(style)) and not CLIP_TEXT.search(style)


ATTRS = ("alt", "title", "aria-label", "aria-description", "placeholder", "content", "data-ai", "data-llm")
# Elements that do not break a line of text: text split across them is joined with a space.
INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "dfn", "em", "font", "i", "kbd", "mark", "q", "s", "samp",
          "small", "span", "strong", "sub", "sup", "time", "u", "var", "wbr"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIP = {"script", "style", "noscript", "template"}


@dataclass
class Channels:
    """Text of one page, split by whether a reader sees it."""

    visible: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)
    hidden_by_css: list[str] = field(default_factory=list)  # hidden only by stylesheet rules (often UI)
    comments: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    structured: list[str] = field(default_factory=list)
    noscript: list[str] = field(default_factory=list)
    user_content: list[str] = field(default_factory=list)  # visible text inside comments, reviews, forum replies


# Containers for text that visitors, not the site, wrote (comments, reviews, replies, forum posts): a
# third-party planting zone (0.3.0). Matched on class and id tokens, and on schema.org microdata.
UGC_TOKEN = re.compile(
    r"(?:^|[-_])(?:comments?|commtext|reply|replies|reviews?|testimonials?|ugc|usercontent|user-content|guestbook"
    r"|forum-post|post-reply|answers?|answer-body|discussion|disqus)(?:$|[-_])",
    re.I,
)
UGC_ITEMTYPE = re.compile(r"schema\.org/(?:Review|Comment|Answer|UserComments)\b", re.I)


def is_user_content(attrs: dict[str, str]) -> bool:
    """Whether an element's attributes mark it as a container for visitor-written text."""
    tokens = attrs.get("class", "").split() + attrs.get("id", "").split()
    if any(UGC_TOKEN.search(t) for t in tokens):
        return True
    if attrs.get("itemprop", "").lower() in ("review", "comment", "suggestedanswer", "acceptedanswer"):
        return True
    return bool(UGC_ITEMTYPE.search(attrs.get("itemtype", "")))


_SIMPLE_SELECTOR = re.compile(r"^([a-z][a-z0-9-]*)?((?:[.#][A-Za-z_][\w-]*)+)$|^([a-z][a-z0-9-]*)$", re.I)


def _strip_comments(css: str) -> str:
    out, i = [], 0
    while True:
        start = css.find("/*", i)
        if start < 0:
            out.append(css[i:])
            return "".join(out)
        out.append(css[i:start])
        end = css.find("*/", start + 2)
        if end < 0:
            return "".join(out)  # unterminated comment runs to the end
        i = end + 2


def css_rules(css: str, _level: int = 0) -> list[tuple[str, str]]:
    """Return ``(selectors, declarations)`` for the top-level rules of a stylesheet.

    One pass over the text, tracking brace depth, so the time is linear in the stylesheet's size
    whatever it contains (an earlier regex version took tens of seconds on a 40 KB stylesheet with
    nested ``@keyframes``). Rules inside ``@layer`` and ``@supports`` blocks are read, since they
    apply to the whole page; other at-rule blocks (``@media``, ``@keyframes``, ``@container``...)
    are skipped at any depth. Unbalanced braces don't derail the rules after them.
    """
    if _level == 0:
        css = _strip_comments(css)
    rules: list[tuple[str, str]] = []
    depth, start, selector, body_start, nested = 0, 0, "", 0, False
    i, n = -1, len(css)
    while i + 1 < n:
        i += 1
        ch = css[i]
        if ch == "\\":  # an escaped character (\{ or \' in a selector) is literal
            i += 1
            continue
        if ch in "\"'":  # a quoted string may hold braces: skip to its closing quote
            j = i + 1
            while j < n and css[j] != ch and css[j] != "\n":
                j += 2 if css[j] == "\\" else 1
            i = j
            continue
        if ch == "{":
            if depth == 0:
                selector, body_start, nested = css[start:i], i + 1, False
            else:
                nested = True
            depth += 1
        elif ch == "}":
            if depth == 0:
                start = i + 1  # stray closing brace: ignore it
                continue
            depth -= 1
            if depth == 0:
                body = css[body_start:i]
                name = selector.strip().split(None, 1)[0].lower() if selector.strip() else ""
                if name in ("@layer", "@supports"):
                    if _level < 8:  # these apply to the whole page: read their rules (bounded nesting)
                        rules.extend(css_rules(body, _level + 1))
                elif not name.startswith("@") and not nested:
                    rules.append((selector.strip(), body))
                start = i + 1
        elif ch == ";" and depth == 0:
            start = i + 1  # a statement at-rule such as @import ...;
    return rules


@dataclass(frozen=True)
class Compound:
    """One compound selector: ``div.a.b#c[data-x="y"]``. Empty fields match anything."""

    tag: str = ""
    classes: frozenset[str] = frozenset()
    ids: frozenset[str] = frozenset()
    attrs: tuple[tuple[str, str, str], ...] = ()  # (name, operator, value); operator "" means present

    def matches(self, el: Element) -> bool:
        if self.tag and self.tag != "*" and self.tag != el.tag:
            return False
        if not self.classes <= el.classes or (self.ids and self.ids != {el.ident}):
            return False
        return all(_attr_matches(el.attrs.get(n), op, v) for n, op, v in self.attrs)


@dataclass(frozen=True)
class Element:
    """What a selector can see of one element."""

    tag: str
    classes: frozenset[str]
    ident: str
    attrs: dict


def _attr_matches(have: str | None, op: str, want: str) -> bool:
    if have is None:
        return False
    if op == "":
        return True
    if op == "=":
        return have == want
    if op == "~=":
        return want in have.split()
    if op == "|=":
        return have == want or have.startswith(want + "-")
    if op == "^=":
        return bool(want) and have.startswith(want)
    if op == "$=":
        return bool(want) and have.endswith(want)
    if op == "*=":
        return bool(want) and want in have
    return False


_COMPOUND = re.compile(r"(\*|[a-z][a-z0-9-]*)?((?:[.#][A-Za-z_][\w-]*|\[[^\]\s]+\])*)", re.I)
_PART = re.compile(r"([.#])([A-Za-z_][\w-]*)|\[([\w-]+)(?:([~|^$*]?=)(?:\"([^\"]*)\"|'([^']*)'|([^\]]*)))?\]")
MAX_COMPOUNDS = 6


def parse_selector(text: str) -> tuple[tuple[str, Compound], ...] | None:
    """Parse one selector into ``((combinator, compound), ...)``, left to right.

    Read: type, class, id and attribute selectors, joined by descendant (space) or child (``>``)
    combinators. Not read (``None``): pseudo-classes and pseudo-elements (``:hover``, ``::before``),
    sibling combinators (``+``, ``~``), attribute values containing spaces, and chains longer than
    ``MAX_COMPOUNDS``. A selector PageVet can't read is skipped, never guessed.
    """
    text = text.strip()
    if not text or ":" in text or "+" in text or "~" in text.replace("~=", ""):
        return None
    tokens = re.sub(r"\s*>\s*", " > ", text).split()
    out: list[tuple[str, Compound]] = []
    comb = ""
    for tok in tokens:
        if tok == ">":
            if not out or comb == ">":
                return None
            comb = ">"
            continue
        m = _COMPOUND.fullmatch(tok)
        if not m or not tok:
            return None
        classes, ids, attrs = set(), set(), []
        for part in _PART.finditer(m.group(2) or ""):
            if part.group(1) == ".":
                classes.add(part.group(2))
            elif part.group(1) == "#":
                ids.add(part.group(2))
            else:
                value = next((g for g in part.group(5, 6, 7) if g is not None), "")
                attrs.append((part.group(3).lower(), part.group(4) or "", value))
        out.append((comb or (" " if out else ""), Compound((m.group(1) or "").lower(), frozenset(classes), frozenset(ids), tuple(attrs))))
        comb = ""
    if not out or comb or len(out) > MAX_COMPOUNDS:
        return None
    return tuple(out)


def selector_matches(selector: tuple[tuple[str, Compound], ...], chain: list[Element]) -> bool:
    """Whether ``selector`` matches the last element of ``chain`` (its ancestors before it)."""
    *rest, (comb, last) = selector
    if not chain or not last.matches(chain[-1]):
        return False
    return _match_up(rest, comb, chain[:-1])


def _match_up(rest: list[tuple[str, Compound]], comb: str, ancestors: list[Element]) -> bool:
    if not rest:
        return True
    *before, (prev_comb, compound) = rest
    if comb == ">":
        return bool(ancestors) and compound.matches(ancestors[-1]) and _match_up(before, prev_comb, ancestors[:-1])
    return any(compound.matches(ancestors[i]) and _match_up(before, prev_comb, ancestors[:i]) for i in range(len(ancestors) - 1, -1, -1))


def hiding_selectors(css: str) -> list[tuple[tuple[str, Compound], ...]]:
    """Return the selectors in a stylesheet whose rules hide an element (see ``parse_selector``).

    Rules inside ``@media`` blocks are skipped (``css_rules``), and a later rule that shows the
    element again is not taken into account. A selector whose last part is ``html``, ``body`` or
    ``head`` is dropped: hiding the whole page until scripts load is common and says nothing about
    any one passage.
    """
    out = []
    for selectors, body in css_rules(css):
        if not hides(body + ";"):
            continue
        for sel in selectors.split(","):
            parsed = parse_selector(sel)
            if parsed and parsed[-1][1].tag not in ("html", "body", "head"):
                out.append(parsed)
    return out


class _Splitter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ch = Channels()
        self.stack: list[tuple[str, int]] = []  # (tag, hiding): 0 shown, 1 by stylesheet rules, 2 inline or markup
        self.chain: list[Element] = []  # the open elements, for stylesheet selectors
        self.ld_json = False
        self.joinable: list[str] | None = None  # the list whose last chunk the next inline text continues
        self.hiding: list[tuple[str, set[str], set[str]]] = []  # from <style> blocks seen so far
        self.ugc: list[bool] = []  # parallel to stack: the element opens a user-content zone

    def _hidden(self) -> int:
        return max((h for _, h in self.stack), default=0)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in INLINE:
            self.joinable = None
        a = {k.lower(): v or "" for k, v in attrs}
        el = Element(tag, frozenset(a.get("class", "").split()), a.get("id", ""), a)
        hidden = 2 if (
            "hidden" in a
            or a.get("aria-hidden", "").lower() == "true"
            or hides(a.get("style", ""))
            or tag in SKIP
        ) else 1 if self._hidden_by_stylesheet(el) else 0
        for name in ATTRS:
            if a.get(name, "").strip() and not (name == "content" and tag != "meta"):
                self.ch.attributes.append(f"{tag}[{name}]: {a[name].strip()}")
        if tag == "input" and a.get("type", "").lower() == "hidden" and a.get("value", "").strip():
            self.ch.attributes.append(f"input[type=hidden][value]: {a['value'].strip()}")
        in_svg = any(t == "svg" for t, _ in self.stack)
        if in_svg and tag in ("title", "desc", "metadata"):
            hidden = 2  # SVG titles show only as a tooltip; desc and metadata are never drawn
        if tag == "script":
            self.ld_json = "ld+json" in a.get("type", "").lower()
        if tag not in VOID:
            self.stack.append((tag, hidden))
            self.chain.append(el)
            self.ugc.append(is_user_content(a))

    def _hidden_by_stylesheet(self, el: Element) -> bool:
        if not self.hiding:
            return False
        chain = [*self.chain, el]
        return any(selector_matches(sel, chain) for sel in self.hiding)

    def handle_endtag(self, tag: str) -> None:
        if tag not in INLINE:
            self.joinable = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                del self.chain[i:]
                del self.ugc[i:]
                break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        tags = [t for t, _ in self.stack]
        if tags and tags[-1] == "style":
            self.hiding.extend(hiding_selectors(text))
            return
        if tags and tags[-1] == "script" and self.ld_json:
            self.ch.structured.extend(json_strings(text))
            return
        if "noscript" in tags and not {"script", "style", "template"} & set(tags):
            self.ch.noscript.append(text)
            return
        if "template" in tags and not {"script", "style"} & set(tags):
            target = self.ch.hidden  # a browser never renders <template> content; text extractors may read it
        elif any(t in SKIP for t in tags):
            return
        else:
            level = self._hidden()
            target = (self.ch.hidden if level == 2 else self.ch.hidden_by_css if level == 1
                      else self.ch.user_content if any(self.ugc) else self.ch.visible)
        if self.joinable is target and target:
            target[-1] += " " + text  # text split across inline elements reads as one run, as a model sees it
        else:
            target.append(text)
        self.joinable = target

    def handle_comment(self, data: str) -> None:
        if data.strip():
            self.ch.comments.append(data.strip())


def json_strings(text: str, limit: int = 5000) -> list[str]:
    """Return the string values inside a JSON-LD block (all of it as one string if it doesn't parse)."""
    try:
        data = json.loads(text)
    except ValueError:
        return [text]
    out: list[str] = []
    todo = [data]
    while todo and len(out) < limit:
        item = todo.pop()
        if isinstance(item, str):
            if item.strip():
                out.append(item.strip())
        elif isinstance(item, dict):
            todo.extend(item.values())
        elif isinstance(item, list):
            todo.extend(item)
    return out[::-1]


def split_html(html: str, css: str = "") -> Channels:
    """Split an HTML page into visible text, hidden text, comments and attributes.

    ``css`` is extra stylesheet text (the page's linked stylesheets, see ``fetch_stylesheets``)
    whose hiding rules apply to the whole page, as rules in ``<style>`` blocks do after they appear.
    """
    parser = _Splitter()
    if css:
        parser.hiding.extend(hiding_selectors(css))
    parser.feed(html)
    parser.close()
    return parser.ch


def looks_like_html(text: str) -> bool:
    """Guess whether ``text`` is an HTML document."""
    return bool(re.search(r"<(?:html|body|div|p|span|head|!--|meta|a\s)[\s>]", text[:5000], re.I))


# Framework IDs for each finding (public 0.2.0). OWASP Top 10 for LLM Applications 2025: LLM01 is prompt
# injection, direct and indirect. MITRE ATLAS: AML.T0051.001 is indirect LLM prompt injection (text planted
# in content a model reads), AML.T0054 LLM jailbreak (role and mode changes), AML.T0068 LLM prompt
# obfuscation (text hidden or disguised from people or filters). Kinds that only say the page differs by
# reader (``content_differs``, ``fetch_differs``) carry no ID: they are a sign to look, not an injection.
OWASP_LLM01 = "LLM01:2025"
ATLAS_INDIRECT, ATLAS_JAILBREAK, ATLAS_OBFUSCATION = "AML.T0051.001", "AML.T0054", "AML.T0068"
_NO_TAXONOMY = {"content_differs", "fetch_differs", "repetition"}
_DISGUISES = ("unicode_tags", "base64", "obfuscated", "rot13", "reversed")


def taxonomy(channel: str, kinds: list[str]) -> dict:
    """Return ``{"owasp": [...], "atlas": [...]}`` for a finding's channel and pattern kinds."""
    plain = {k.split(":")[-1] for k in kinds}
    if plain <= _NO_TAXONOMY:
        return {"owasp": [], "atlas": []}
    atlas = [ATLAS_INDIRECT]
    if "role_change" in plain:
        atlas.append(ATLAS_JAILBREAK)
    hidden = channel not in READER_CHANNELS and channel not in ("llms.txt",)
    if hidden or any(k.startswith(_DISGUISES) for k in kinds):
        atlas.append(ATLAS_OBFUSCATION)
    return {"owasp": [OWASP_LLM01], "atlas": atlas}


@dataclass
class Finding:
    """One channel of one page where the check matched."""

    channel: str
    kinds: list[str]
    excerpt: str
    severity: str = "low"
    advice: str = ""
    opinions: dict = field(default_factory=dict)
    taxonomy: dict = field(default_factory=dict)
    intent: str = ""  # "commercial" when the instruction steers recommendations, rankings or citations (0.3.0)

    def __post_init__(self) -> None:
        if not self.taxonomy:
            self.taxonomy = taxonomy(self.channel, self.kinds)


@dataclass
class PageResult:
    """What the scan found on one page."""

    source: str
    findings: list[Finding]
    error: str = ""
    evidence: dict = field(default_factory=dict)


def _excerpt(text: str, start: int, width: int = 160) -> str:
    lo = max(0, start - 40)
    snippet = re.sub(r"\s+", " ", text[lo : lo + width]).strip()
    snippet = "".join(ch for ch in snippet if ch.isprintable())
    return ("…" if lo else "") + snippet + ("…" if lo + width < len(text) else "")


def scan_text(source: str, text: str, include_repetition: bool = False, css: str = "") -> PageResult:
    """Scan one page's text, channel by channel when it is HTML.

    A channel whose only finding is ``repetition`` (mostly one repeated claim) is dropped unless
    ``include_repetition`` is set: on 194 ordinary pages (docs/bench/2026-11-19-clean-pages/) that
    rule alone flagged 21, all menu and template boilerplate, and nothing else. ``css`` is passed
    to ``split_html``.
    """
    if looks_like_html(text):
        ch = split_html(text, css)
        channels = {
            "visible text": "\n".join(ch.visible),
            "user-submitted content": "\n".join(ch.user_content),
            "hidden elements": "\n".join(ch.hidden),
            "hidden by stylesheet rules": "\n".join(ch.hidden_by_css),
            "HTML comments": "\n".join(ch.comments),
            "attributes and meta tags": "\n".join(ch.attributes),
            "structured data (JSON-LD)": "\n".join(ch.structured),
            "noscript": "\n".join(ch.noscript),
        }
    else:
        channels = {"text": text}
    return scan_channels(source, channels, include_repetition)


def scan_channels(source: str, channels: dict[str, str], include_repetition: bool = False) -> PageResult:
    """Scan named channels of one document; channels in ``READER_CHANNELS`` are rated as visible."""
    findings = []
    for name, body in channels.items():
        hits = scan(body)
        if name not in READER_CHANNELS:
            # Hidden channels: report the instruction kinds, not CSS hints that only matter in raw HTML.
            hits = [h for h in hits if h.kind not in HIDDEN_PATTERNS]
        if hits:
            first = min(hits, key=lambda h: h.start)
            kinds = sorted({h.kind for h in hits})
            if kinds == ["repetition"] and not include_repetition:
                continue
            excerpt = _excerpt(body, first.start)
            severity, advice = rate(name, kinds, body)
            instruction = [h for h in hits if h.kind.split(":")[-1] in INSTRUCTION_PATTERNS]
            intent = "commercial" if any(commercial(body, h.start) for h in instruction) else ""
            if intent:
                advice += " It steers what AI answers recommend, rank or cite (commercial manipulation)."
            findings.append(Finding(name, kinds, excerpt, severity, advice, intent=intent))
    return PageResult(source, findings)


# --- Severity ------------------------------------------------------------------------------------

SEVERITIES = ("low", "medium", "high")
READER_CHANNELS = {"visible text", "user-submitted content", "text", "PDF text", "text in images"}
ENCODED = ("unicode_tags", "base64", "obfuscated", "rot13", "reversed")
# Words that suggest a page is writing about injection rather than attempting it.
DISCUSSION = re.compile(
    r"prompt[- ]injection|jailbreak|\battack(?:s|ers?)?\b|\bexample(?:s)?\b|researchers?|vulnerabilit|"
    r"such as\s+[\"\u201c']|security (?:team|research|advisory)|red[- ]team",
    re.I,
)


def rate(channel: str, kinds: list[str], body: str) -> tuple[str, str]:
    """Rate one finding and say what to do about it. Fixed rules, no model.

    - high: an instruction a reader can't see (hidden element, comment, attribute, structured
      data, noscript) or one encoded in invisible Unicode or base64. Concealment plus an
      instruction is the pattern of a deliberate attempt. Exception: in text hidden only by
      stylesheet rules (dialogs, menus, collapsed forms), a match of only the weakest pattern (a
      command about the reply) is medium.
    - medium: an instruction in text a reader sees, with no sign the page is discussing injection.
    - low: a page that is only repetitive, or visible text that reads as discussion or a quoted
      example (it names prompt injection, attacks, examples or researchers).
    """
    encoded = any(k.startswith(ENCODED) for k in kinds)
    kinds = [k.removeprefix("split:") for k in kinds]  # joined fragments rate like the plain kind
    only_repetition = set(kinds) <= {"repetition"}
    if encoded:
        return "high", "Remove the disguised, encoded or invisible text; readers cannot see or read it, and AI systems can."
    if channel == "llms.txt":
        # llms.txt is written for AI systems, so text addressed to them is expected there. Overrides, role
        # changes and chat markup are not; telling assistants what to say or leave out is worth a look.
        if set(kinds) & {"override", "role_change", "chat_markup"}:
            return "high", "llms.txt tries to override an AI system's instructions or role. Remove that text; llms.txt should describe the site."
        if only_repetition:
            return "low", "Review the repeated text in llms.txt."
        return "low", ("llms.txt addresses AI systems, as it is meant to. Check that it describes the site and its "
                       "content rather than telling assistants what to recommend, cite or leave out.")
    if channel not in READER_CHANNELS:
        if only_repetition:
            return "low", f"Review the repeated text in {channel}."
        if channel == "hidden by stylesheet rules" and set(kinds) <= {"response_directive", "repetition"}:
            # Stylesheets hide dialogs, menus and collapsed reply forms ("Add your reply"), which match
            # the weakest pattern; text hidden inline or by markup stays high.
            return "medium", ("Text hidden by the page's stylesheet tells the reader how to word a reply. Often a "
                              "collapsed form or dialog; if it is not for people, remove it.")
        return "high", f"Remove the instruction from {channel}, or make it visible, ordinary content. Hidden text aimed at AI is treated as manipulation."
    if only_repetition:
        return "low", "The page is mostly one repeated claim; AI systems may discount or distrust it. Add substantive content."
    if set(kinds) <= {"response_directive", "repetition"}:
        return "low", "Text tells the reader how to word a reply. Often ordinary (forms, support pages, quizzes); check it is meant for people."
    if DISCUSSION.search(body):
        return "low", "Reads as discussion or a quoted example of prompt injection. No action if that is the page's purpose."
    if channel == "user-submitted content":
        return "medium", ("Text in a comment, review or forum reply addresses AI systems or tells them what to do. A visitor may "
                          "have planted it: moderate or remove it, and check other user-submitted text on the site.")
    return "medium", "Visible text addresses AI systems or tells them what to do. Reword it as content for readers, or remove it."


def add_opinions(results: list[PageResult], detector: object) -> int:
    """Attach ``detector``'s verdict to every low and medium finding; return how many were judged.

    High findings (hidden, encoded or cloaked instructions) are not sent: the rule already decides
    them. The opinion is recorded beside the rule-based severity and never changes it.
    """
    targets = [f for r in results for f in r.findings if f.severity != "high" and not f.channel.startswith("served to ")]
    if not targets:
        return 0
    for finding, verdict in zip(targets, detector.judge([f.excerpt for f in targets]), strict=True):
        finding.opinions[verdict.detector] = {"flagged": verdict.flagged, "score": verdict.score}
    return len(targets)


def at_least(findings: list[Finding], level: str) -> list[Finding]:
    """Return the findings at or above ``level``."""
    floor = SEVERITIES.index(level)
    return [f for f in findings if SEVERITIES.index(f.severity) >= floor]


# --- AI-crawler comparison ---------------------------------------------------------------------

BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
# Product tokens the crawlers announce; a site that cloaks by user agent matches on these.
CRAWLER_UAS = {
    "GPTBot": "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)",
    "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
}


def _visible_text(body: str) -> str:
    return "\n".join(split_html(body).visible) if looks_like_html(body) else body


def compare_agents(url: str, agent_fetch: Callable[[str, str], str], threshold: float = 0.9) -> list[Finding]:
    """Fetch ``url`` as a browser and as AI crawlers; report crawlers that are served different content.

    A difference is reported when the visible text is less than ``threshold`` similar to the
    browser's, or when the crawler's copy has findings the browser's copy does not. Detects
    cloaking by user agent only: a site that cloaks by IP address looks identical here.
    """
    import difflib

    base = agent_fetch(url, BROWSER_UA)
    base_text = _visible_text(base)
    base_keys = {(f.channel, tuple(f.kinds)) for f in scan_text(url, base).findings}
    out: list[Finding] = []
    for name, ua in CRAWLER_UAS.items():
        try:
            body = agent_fetch(url, ua)
        except Exception as exc:  # a crawler being refused is itself worth reporting
            out.append(Finding(f"served to {name}", ["fetch_differs"], _err(exc), "low",
                               f"{name} could not fetch the page a browser could; check robots and firewall rules if that is not intended."))
            continue
        text = _visible_text(body)
        ratio = difflib.SequenceMatcher(None, base_text[:20000], text[:20000], autojunk=False).ratio()
        extra = [f for f in scan_text(url, body).findings
                 if (f.channel, tuple(f.kinds)) not in base_keys and not set(f.kinds) <= {"repetition"}]
        if extra:
            kinds = sorted({k for f in extra for k in f.kinds})
            out.append(Finding(f"served to {name}", ["cloaked_instruction", *kinds], extra[0].excerpt, "high",
                               f"{name} is served instructions a browser is not. Serve AI crawlers the same content as readers."))
        elif ratio < threshold:
            out.append(Finding(f"served to {name}", ["content_differs"], f"visible text is {ratio:.0%} similar to the browser's copy",
                               "medium", f"{name} is served different content from a browser. Confirm this is intended (cloaking can be penalized)."))
    return out


def _refuse_private(request: object) -> None:
    """Refuse a request (including each redirect) to a loopback, private or link-local address."""
    import ipaddress
    import socket

    host = request.url.host  # type: ignore[attr-defined]
    for info in socket.getaddrinfo(host, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"refusing to fetch {host}: it resolves to a non-public address")


def fetch(url: str, timeout: float = 20.0, allow_private: bool = True, max_bytes: int | None = None,
          user_agent: str | None = None) -> str:
    """Fetch a URL over http(s) and return its body as text.

    ``allow_private=False`` refuses hosts that resolve to non-public addresses, checked on every
    redirect; the MCP tool uses it, since an agent chooses the URL there. ``max_bytes`` stops
    reading the body after that many bytes (sitemaps use it).
    """
    import httpx

    if not re.match(r"https?://", url, re.I):
        raise ValueError("only http(s) URLs are fetched")
    headers = {"User-Agent": user_agent or "pagevet (page audit for text aimed at AI models)"}
    hooks = {} if allow_private else {"request": [_refuse_private]}
    deadline = time.monotonic() + 3 * timeout  # timeout applies per read; this bounds the whole fetch
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers, event_hooks=hooks) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            data = bytearray()
            for chunk in resp.iter_bytes():
                data.extend(chunk)
                if max_bytes is not None and len(data) >= max_bytes:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{url}: still downloading after {3 * timeout:.0f} s")
            body = bytes(data if max_bytes is None else data[:max_bytes])
            return body.decode(resp.encoding or "utf-8", errors="replace")


# Response headers that carry machine values (dates, sizes, cache and routing tokens, cookies, policies). The
# rest, including custom X- headers, are scanned with --headers.
HEADER_SKIP = frozenset({
    "accept-ranges", "age", "alt-svc", "cache-control", "cf-cache-status", "cf-ray", "connection", "content-encoding",
    "content-length", "content-type", "date", "etag", "expires", "last-modified", "nel", "pragma", "report-to",
    "server-timing", "set-cookie", "strict-transport-security", "transfer-encoding", "vary", "via", "x-cache",
    "x-cache-hits", "x-request-id", "x-served-by", "x-timer", "x-amz-cf-id", "x-amz-cf-pop", "x-amz-request-id",
    "x-amz-id-2", "content-security-policy", "content-security-policy-report-only", "permissions-policy",
})
MAX_HEADER_TEXT = 20_000


def fetch_headers(url: str, timeout: float = 10.0, user_agent: str | None = None) -> dict[str, str]:
    """Return the final response's headers for a GET of ``url`` (the body is not read)."""
    import httpx

    if not re.match(r"https?://", url, re.I):
        raise ValueError("only http(s) URLs are fetched")
    headers = {"User-Agent": user_agent or "pagevet (page audit for text aimed at AI models)"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            return dict(resp.headers.items())


def header_text(headers: dict[str, str]) -> str:
    """The scannable part of a response's headers, one ``Name: value`` line each."""
    lines = [f"{k}: {v}" for k, v in headers.items() if k.lower() not in HEADER_SKIP]
    return "\n".join(lines)[:MAX_HEADER_TEXT]


# --- Text in images (0.5.0, --ocr) ----------------------------------------------------------------
MAX_OCR_IMAGES = 10
MAX_IMAGE_BYTES = 5_000_000
_IMG = re.compile(r"<img\b[^>]*>", re.I)
_DATA_IMAGE = re.compile(r"data:image/(?:png|jpe?g|gif|webp|bmp);base64,([A-Za-z0-9+/=\s]+)", re.I)
# OCR reads a capital I as a small l or a 1 in "AI" often enough to matter for the patterns.
_OCR_AI = re.compile(r"\bA[l1|]\b")


def image_sources(page_html: str, base_url: str, limit: int = MAX_OCR_IMAGES) -> list[str]:
    """The page's ``<img>`` sources (``src``, else the first ``srcset`` entry), absolute, at most ``limit``."""
    from urllib.parse import urljoin

    out: list[str] = []
    for tag in _IMG.findall(page_html):
        attrs = {m.group(1).lower(): next(g for g in m.groups()[1:] if g is not None) for m in _ATTR.finditer(tag)}
        src = attrs.get("src") or (attrs.get("srcset", "").split(",")[0].split() or [""])[0]
        if not src:
            continue
        url = src if src.startswith("data:") else urljoin(base_url, src)
        if (url.startswith("data:image/") or re.match(r"https?://", url, re.I)) and url not in out:
            out.append(url)
        if len(out) >= limit:
            break
    return out


def default_ocr(data: bytes) -> str:  # pragma: no cover - needs the optional extra and a model download
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        from pagevet import install_hint

        raise RuntimeError(f"--ocr needs the optional extra: {install_hint('ocr')}") from exc
    global _OCR_ENGINE
    if "_OCR_ENGINE" not in globals():
        _OCR_ENGINE = RapidOCR()
    result, _ = _OCR_ENGINE(data)
    return " ".join(r[1] for r in (result or []))


def ocr_text(sources: list[str], image_fetcher: Callable[[str], bytes], ocr: Callable[[bytes], str]) -> tuple[str, list[str]]:
    """OCR each image; return the text (one line per image) and notes for images that could not be read."""
    import base64

    lines, notes = [], []
    for src in sources:
        try:
            m = _DATA_IMAGE.match(src)
            data = base64.b64decode(m.group(1)) if m else image_fetcher(src)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("image larger than 5 MB")
            text = _OCR_AI.sub("AI", ocr(data)).strip()
            if text:
                lines.append(text)
        except Exception as exc:  # one image failing must not lose the others
            notes.append(f"{src[:80]}: not read ({type(exc).__name__})")
    return "\n".join(lines), notes


LLMS_FILES = ("llms.txt", "llms-full.txt")
MAX_LLMS_BYTES = 2_000_000


def site_root(url: str) -> str:
    """``https://host`` for a page URL."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


MAX_PDF_BYTES = 20_000_000


def fetch_bytes(url: str, timeout: float = 30.0, allow_private: bool = True, max_bytes: int = MAX_PDF_BYTES) -> bytes:
    """Fetch a URL over http(s) and return up to ``max_bytes`` of its body (for PDFs)."""
    import httpx

    if not re.match(r"https?://", url, re.I):
        raise ValueError("only http(s) URLs are fetched")
    hooks = {} if allow_private else {"request": [_refuse_private]}
    headers = {"User-Agent": "pagevet (page audit for text aimed at AI models)"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers, event_hooks=hooks) as client:
        deadline = time.monotonic() + 3 * timeout
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            data = bytearray()
            for chunk in resp.iter_bytes():
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise ValueError(f"PDF larger than {max_bytes:,} bytes")
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{url}: still downloading after {3 * timeout:.0f} s")
            return bytes(data)


def is_pdf_source(source: str) -> bool:
    return bool(re.search(r"\.pdf(?:$|[?#])", source, re.I))


def pdf_channels(data: bytes) -> dict[str, str]:
    """Split a PDF into the text a reader sees and the text a reader normally doesn't.

    "PDF text" is the extracted page text. "PDF metadata and annotations" holds the document
    information (title, subject, keywords, author...), XMP metadata and annotation contents, which
    viewers don't show on the page but text extractors and AI tools read. Needs the ``pdf`` extra.
    Text drawn invisibly on the page (white, tiny, off-page) is extracted as ordinary page text.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(f"reading PDFs needs the optional extra: {install_hint('pdf')}") from exc
    import io
    import logging

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # malformed-content warnings are not findings
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF (no %PDF header)")
    reader = PdfReader(io.BytesIO(data))
    pages, hidden = [], []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            for key in ("/Contents", "/T", "/TU"):
                if obj.get(key):
                    hidden.append(f"annotation{key}: {obj[key]}")
    for key, value in (reader.metadata or {}).items():
        if isinstance(value, str) and value.strip():
            hidden.append(f"metadata{key}: {value.strip()}")
    import contextlib

    with contextlib.suppress(Exception):  # malformed XMP: skip it, keep the rest
        xmp = reader.xmp_metadata
        for name in ("dc_title", "dc_description", "dc_subject"):
            value = getattr(xmp, name, None) if xmp is not None else None
            if value:
                hidden.append(f"xmp {name}: {value}")
    return {"PDF text": "\n".join(pages), "PDF metadata and annotations": "\n".join(hidden)}


def scan_pdf(source: str, data: bytes, include_repetition: bool = False) -> PageResult:
    """Scan a PDF's page text (rated as visible) and its metadata and annotations (rated as hidden)."""
    return scan_channels(source, pdf_channels(data), include_repetition)


def read_source(source: str, fetcher: Fetcher | None = None) -> str:
    """Read a file path, ``-`` for stdin, or an http(s) URL."""
    if source == "-":
        return sys.stdin.read()
    if _is_url(source):
        return (fetcher or fetch)(source)
    return Path(source).read_text(encoding="utf-8", errors="replace")


MAX_STYLESHEETS = 5
MAX_STYLESHEET_BYTES = 1_000_000
_LINK = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)


def stylesheet_links(page_html: str, base_url: str, limit: int = MAX_STYLESHEETS, any_host: bool = False) -> list[str]:
    """Return up to ``limit`` stylesheet URLs a page links to (http or https), on its own host
    unless ``any_host``."""
    from urllib.parse import urljoin, urlsplit

    host = urlsplit(base_url).hostname
    out: list[str] = []
    for tag in _LINK.findall(page_html):
        attrs = {m.group(1).lower(): next(g for g in m.groups()[1:] if g is not None) for m in _ATTR.finditer(tag)}
        if "stylesheet" not in attrs.get("rel", "").lower().split() or not attrs.get("href"):
            continue
        url = urljoin(base_url, html.unescape(attrs["href"]))
        parts = urlsplit(url)
        if parts.scheme in ("http", "https") and (any_host or parts.hostname == host) and url not in out:
            out.append(url)
        if len(out) >= limit:
            break
    return out


def fetch_stylesheets(page_html: str, page_url: str, css_fetcher: Fetcher | None = None,
                      any_host: bool = False) -> tuple[str, list[str]]:
    """Fetch a page's own linked stylesheets; return their text joined, and one note per failure.

    Only stylesheets on the page's host are read unless ``any_host`` (CDNs), at most
    ``MAX_STYLESHEETS`` of ``MAX_STYLESHEET_BYTES`` each. ``@import`` is not followed.
    """
    get = css_fetcher or (lambda u: fetch(u, timeout=10.0, max_bytes=MAX_STYLESHEET_BYTES))
    sheets, notes = [], []
    for url in stylesheet_links(page_html, page_url, any_host=any_host):
        try:
            sheets.append(get(url)[:MAX_STYLESHEET_BYTES])
        except Exception as exc:  # a missing stylesheet must not lose the page
            notes.append(f"stylesheet {url} not read: {_err(exc)}")
    return "\n".join(sheets), notes


ROBOTS_AGENT = "pagevet"


class Robots:
    """robots.txt answers per host for ``ROBOTS_AGENT``, fetched once per host.

    A robots.txt that can't be fetched (missing, an error, a timeout) allows everything, as
    crawlers conventionally treat it. ``fetcher`` replaces the plain HTTP fetch, for tests.
    """

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self._get = fetcher or (lambda u: fetch(u, timeout=10.0, max_bytes=500_000))
        self._cache: dict[str, object] = {}

    def allowed(self, url: str) -> bool:
        import urllib.robotparser
        from urllib.parse import urlsplit

        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._cache:
            parser = urllib.robotparser.RobotFileParser()
            try:
                parser.parse(self._get(root + "/robots.txt").splitlines())
            except Exception:  # unreadable robots.txt: allow
                parser.parse([])
            self._cache[root] = parser
        return self._cache[root].can_fetch(ROBOTS_AGENT, url)  # type: ignore[attr-defined]


def _is_url(source: str) -> bool:
    return bool(re.match(r"https?://", source, re.I))


# --- Many pages: sitemaps and URL lists ---------------------------------------------------------


def _read_capped(source: str, fetcher: Fetcher | None) -> str:
    """Read a sitemap from a URL or a file, refusing anything over ``MAX_SITEMAP_BYTES``."""
    if _is_url(source):
        text = fetcher(source) if fetcher else fetch(source, max_bytes=MAX_SITEMAP_BYTES + 1)
        if len(text.encode("utf-8", errors="replace")) > MAX_SITEMAP_BYTES:
            raise ValueError(f"sitemap is larger than {MAX_SITEMAP_BYTES:,} bytes")
        return text
    with open(source, "rb") as fh:
        data = fh.read(MAX_SITEMAP_BYTES + 1)
    if len(data) > MAX_SITEMAP_BYTES:
        raise ValueError(f"sitemap is larger than {MAX_SITEMAP_BYTES:,} bytes")
    return data.decode("utf-8", errors="replace")


def parse_sitemap(xml_text: str) -> tuple[str, list[str]]:
    """Parse a sitemap; return ``("urlset" | "sitemapindex", [<loc> values])``.

    Parsed with defusedxml (no external entities, no entity expansion). Sitemaps have no use for a
    DTD, so any ``<!DOCTYPE`` or ``<!ENTITY`` is refused outright, which also rules out
    internal entity-expansion bombs.
    """
    if re.search(r"<!(?:DOCTYPE|ENTITY)", xml_text, re.I):
        raise ValueError("sitemap contains a DTD or entity declaration; refused")
    # defusedxml refuses entity expansion and external entities (XXE, billion laughs); the size
    # cap is applied by the caller before parsing.
    root = safe_fromstring(xml_text.strip())
    kind = root.tag.rsplit("}", 1)[-1].lower()
    if kind not in ("urlset", "sitemapindex"):
        raise ValueError(f"not a sitemap (root element <{kind}>)")
    locs = [el.text.strip() for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "loc" and el.text and el.text.strip()]
    return kind, locs


def sitemap_urls(source: str, fetcher: Fetcher | None = None) -> tuple[list[str], list[PageResult]]:
    """Return the page URLs in a sitemap, following a sitemap index one level deep.

    Returns ``(urls, errors)``; a child sitemap that cannot be read becomes an error result and
    the others are still used. A child that is itself an index is not followed. Page ``<loc>``
    values must be http(s) URLs, so a sitemap cannot make the scan read local files; a child
    sitemap may be a local path only when the index itself is a local file.
    """
    kind, locs = parse_sitemap(_read_capped(source, fetcher))
    errors: list[PageResult] = []

    def pages(values: list[str], origin: str) -> list[str]:
        bad = [v for v in values if not _is_url(v)]
        if bad:
            errors.append(PageResult(origin, [], f"skipped {len(bad)} <loc> value(s) that are not http(s) URLs"))
        return [v for v in values if _is_url(v)]

    if kind == "urlset":
        return pages(locs, source), errors
    urls: list[str] = []
    for child in locs[:MAX_CHILD_SITEMAPS]:
        try:
            if _is_url(source) and not _is_url(child):
                raise ValueError("a remote sitemap index may only point to http(s) sitemaps")
            child_kind, child_locs = parse_sitemap(_read_capped(child, fetcher))
            if child_kind == "sitemapindex":
                raise ValueError("nested sitemap index not followed (one level deep only)")
            urls.extend(pages(child_locs, child))
        except Exception as exc:  # report and keep going
            errors.append(PageResult(child, [], _err(exc)))
    if len(locs) > MAX_CHILD_SITEMAPS:
        errors.append(PageResult(source, [], f"only the first {MAX_CHILD_SITEMAPS} of {len(locs)} child sitemaps were read"))
    return urls, errors


def read_url_list(path: str) -> list[str]:
    """Read one URL per line, skipping blank lines and ``#`` comments."""
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8", errors="replace")
    return [s for line in text.splitlines() if (s := line.strip()) and not s.startswith("#")]


def _err(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:200]


# --- Reports -----------------------------------------------------------------------------------

DISCLAIMER = "Pattern matching only: a clean result is not proof a page is safe."


def render(results: list[PageResult]) -> str:
    """Render results as plain text for a terminal."""
    lines = []
    for r in results:
        if r.error:
            lines.append(f"✗ {r.source}: could not read ({r.error})")
        elif not r.findings:
            lines.append(f"✓ {r.source}: no text aimed at AI models found")
        else:
            lines.append(f"! {r.source}: {len(r.findings)} finding(s)")
            for f in r.findings:
                lines.append(f"    [{f.severity}] {f.channel}: {', '.join(f.kinds)}")
                lines.append(f"      {f.excerpt}")
                lines.append(f"      -> {f.advice}")
                for name, op in f.opinions.items():
                    lines.append(f"      second opinion ({name}): {'flagged' if op['flagged'] else 'not flagged'}, score {op['score']}")
    flagged = sum(1 for r in results if r.findings)
    lines.append(f"\n{flagged} of {len(results)} page(s) contain text aimed at AI models. {DISCLAIMER}")
    return "\n".join(lines)


def render_json(results: list[PageResult]) -> str:
    """Render results as a JSON list, one object per page."""
    return json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False)


def read_evidence(source: str, body: str, via: str = "http") -> dict:
    """What was scanned (0.5.0): SHA-256 of the text read, when, and how. Goes in ``PageResult.evidence``."""
    import hashlib
    from datetime import datetime

    how = ("firecrawl" if via == "firecrawl" else "http") if _is_url(source) else ("stdin" if source == "-" else "file")
    return {"sha256": hashlib.sha256(body.encode("utf-8", "replace")).hexdigest(),
            "fetched_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "fetched_via": how}


def render_receipt(results: list[PageResult]) -> str:
    """A scan receipt (0.5.0, schema docs/schema/receipt.schema.json): what was read, with which rules, and what was
    found, for evidence pipelines such as SourceWatch. Excerpts are left out; findings carry their fingerprints."""
    import hashlib
    from datetime import datetime

    from pagevet.rules import render as render_rules

    pages = []
    for r in results:
        ev = r.evidence or {}
        pages.append({
            "source": r.source, "read": not r.error, "error": r.error,
            "sha256": ev.get("sha256", ""), "fetched_at": ev.get("fetched_at", ""), "fetched_via": ev.get("fetched_via", ""),
            **({"capture_id": ev["capture_id"]} if ev.get("capture_id") else {}),
            "findings": [{"channel": f.channel, "kinds": f.kinds, "severity": f.severity, "intent": f.intent,
                          "taxonomy": f.taxonomy, "fingerprint": finding_fingerprint(r.source, f)} for f in r.findings],
        })
    doc = {"schema": "pagevet-receipt-1", "pagevet": __version__,
           "rules_sha256": hashlib.sha256(render_rules().encode()).hexdigest(),
           "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "pages": pages}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _csv_cell(value: str) -> str:
    # A spreadsheet runs a cell that starts with = + - @ as a formula; page text is untrusted.
    risky = value[:1] in ("=", "+", "-", "@", "\t", "\r") and value != "-"  # "-" is stdin, not a formula
    return "'" + value if risky else value


def render_csv(results: list[PageResult]) -> str:
    """Render results as CSV: one row per finding, plus one per clean page and per error.

    Cells that a spreadsheet would read as a formula are prefixed with ``'``.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["source", "status", "channel", "kinds", "excerpt", "error", "severity", "advice"])
    for r in results:
        if r.error:
            rows = [[r.source, "error", "", "", "", r.error]]
        elif not r.findings:
            rows = [[r.source, "clean", "", "", "", ""]]
        else:
            rows = [[r.source, "finding", f.channel, ";".join(f.kinds), f.excerpt, "", f.severity, f.advice] for f in r.findings]
        for row in rows:
            writer.writerow([_csv_cell(c) for c in row])
    return buf.getvalue()


_CSS = """
.sev-high{color:#b00020;font-weight:700}.sev-medium{color:#9a6700;font-weight:600}.sev-low{color:#555}
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1f2328;line-height:1.5}
h1{font-size:1.6rem;margin-bottom:.25rem}h2{font-size:1.1rem;margin:0 0 .5rem;word-break:break-all}
.meta{color:#59636e;font-size:.9rem}
.summary{display:flex;gap:1rem;flex-wrap:wrap;margin:1.5rem 0}
.stat{border:1px solid #d1d9e0;border-radius:8px;padding:.75rem 1rem;min-width:9rem}
.stat b{display:block;font-size:1.6rem}
.note{background:#fff8c5;border:1px solid #d4a72c;border-radius:8px;padding:.75rem 1rem}
section{border:1px solid #d1d9e0;border-left-width:6px;border-radius:8px;padding:1rem;margin:1rem 0}
section.finding{border-left-color:#cf222e}section.clean{border-left-color:#1a7f37}section.error{border-left-color:#9a6700}
.status{font-weight:600}table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;vertical-align:top;border-top:1px solid #d1d9e0;padding:.4rem .5rem}
td.excerpt{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-word}
"""


def render_html(results: list[PageResult], generated: str | None = None) -> str:
    """Render results as one self-contained HTML page (inline CSS, no scripts, no external assets).

    All page-derived text (sources, excerpts, errors) is escaped with ``html.escape``.
    """
    esc = html.escape
    when = generated or datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    flagged = sum(1 for r in results if r.findings)
    errors = sum(1 for r in results if r.error)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>PageVet audit: text aimed at AI models</title>",
        f"<style>{_CSS}</style></head><body>",
        "<h1>Text aimed at AI models: scan report</h1>",
        f'<p class="meta">Generated {esc(when)} by pagevet. Each page is split into what a reader sees '
        "and what a reader doesn't (hidden elements, HTML comments, attributes and meta tags, structured data, noscript); each channel is "
        "checked for instructions written for AI models.</p>",
        '<div class="summary">',
        f'<div class="stat"><b>{len(results)}</b>pages scanned</div>',
        f'<div class="stat"><b>{flagged}</b>pages with findings</div>',
        f'<div class="stat"><b>{sum(1 for r in results for f in r.findings if f.severity == "high")}</b>high-severity findings</div>',
        f'<div class="stat"><b>{errors}</b>errors</div>',
        "</div>",
        f'<p class="note">{esc(DISCLAIMER)} The check looks for known patterns; text it does not recognise '
        "(paraphrased or translated instructions, for example) can still reach an AI model.</p>",
    ]
    for r in results:
        status = "error" if r.error else "finding" if r.findings else "clean"
        parts.append(f'<section class="{status}"><h2>{esc(r.source)}</h2>')
        if r.error:
            parts.append(f'<p class="status">Could not read: {esc(r.error)}</p>')
        elif not r.findings:
            parts.append('<p class="status">No text aimed at AI models found.</p>')
        else:
            parts.append(f'<p class="status">{len(r.findings)} finding(s)</p>')
            parts.append("<table><tr><th>Severity</th><th>Channel</th><th>Kinds</th><th>Excerpt</th><th>What to do</th></tr>")
            for f in r.findings:
                parts.append(
                    f'<tr><td class="sev-{esc(f.severity)}">{esc(f.severity)}</td><td>{esc(f.channel)}</td>'
                    f"<td>{esc(', '.join(f.kinds))}</td>"
                    f'<td class="excerpt">{esc(f.excerpt)}</td><td>{esc(f.advice)}</td></tr>'
                )
            parts.append("</table>")
        parts.append("</section>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


# OWASP Top 10 for LLM Applications (2025): LLM01 is prompt injection, direct and indirect.
OWASP = "OWASP LLM01:2025 Prompt Injection"
SARIF_LEVEL = {"high": "error", "medium": "warning", "low": "note"}


def render_sarif(results: list[PageResult], baseline: bool = False) -> str:
    """Render results as SARIF 2.1.0, for code-scanning tools such as GitHub's security tab.

    Each result carries a ``partialFingerprints`` entry so code scanning can track it across runs;
    with ``baseline`` set (the scan used ``--baseline``) each result is marked ``baselineState: new``.
    """

    rules: dict[str, dict] = {}
    sarif_results = []
    for r in results:
        for f in r.findings:
            rule_id = "pagevet/" + f.kinds[0].split(":")[0]
            rules.setdefault(rule_id, {
                "id": rule_id,
                "shortDescription": {"text": f"Text aimed at AI models ({f.kinds[0].split(':')[0]})"},
                "helpUri": "https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
                "properties": {"tags": ["security", "prompt-injection", OWASP, *f.taxonomy.get("atlas", []),
                                        *(["commercial-manipulation"] if f.intent == "commercial" else [])]},
            })
            sarif_results.append({
                "ruleId": rule_id,
                "level": SARIF_LEVEL[f.severity],
                "message": {"text": f"{f.channel}: {', '.join(f.kinds)}. {f.advice} Excerpt: {f.excerpt}"},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": r.source}}}],
                "partialFingerprints": {"pagevet/v1": finding_fingerprint(r.source, f)},
                "properties": {"severity": f.severity, "channel": f.channel, "kinds": f.kinds,
                               "owasp": f.taxonomy.get("owasp", []), "atlas": f.taxonomy.get("atlas", []),
                               "intent": f.intent},
                **({"baselineState": "new"} if baseline else {}),
            })
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "pagevet", "version": __version__, "rules": list(rules.values())}},
            "results": sarif_results,
            "invocations": [{"executionSuccessful": True,
                             "toolExecutionNotifications": [{"level": "warning", "message": {"text": f"{r.source}: {r.error}"}}
                                                            for r in results if r.error]}],
        }],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# --- Baseline comparison ----------------------------------------------------------------------


def fingerprint(source: str, channel: str, kinds: list[str], excerpt: str) -> str:
    """Stable id for a finding: page, channel, kinds and excerpt, with whitespace and ellipses ignored.

    Recomputed from those four fields, so reports written by older versions still compare. An edit
    near the matched text changes the excerpt, and the finding then counts as new.
    """
    text = re.sub(r"\s+", " ", excerpt.strip("…").strip())
    key = "\x1f".join([source, channel, ",".join(sorted(kinds)), text])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def finding_fingerprint(source: str, f: Finding) -> str:
    return fingerprint(source, f.channel, f.kinds, f.excerpt)


def load_baseline(path: str) -> dict[str, str]:
    """Read an earlier ``--format json`` report; map each finding's fingerprint to its page."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: not a pagevet JSON report (expected a list of pages)")
    out: dict[str, str] = {}
    for page in data:
        if not isinstance(page, dict) or not isinstance(page.get("findings", []), list):
            raise ValueError(f"{path}: not a pagevet JSON report")
        for f in page.get("findings", []):
            src = str(page.get("source", ""))
            out[fingerprint(src, str(f.get("channel", "")), [str(k) for k in f.get("kinds", [])],
                            str(f.get("excerpt", "")))] = src
    return out


@dataclass
class BaselineDiff:
    new: int = 0
    unchanged: int = 0
    gone: int = 0


def apply_baseline(results: list[PageResult], known: dict[str, str]) -> BaselineDiff:
    """Drop findings already in the baseline, in place; count new, unchanged and gone.

    "Gone" counts baseline findings on pages scanned again (without an error) that no longer appear.
    Pages missing from this scan are not counted as gone.
    """
    diff = BaselineDiff()
    seen: set[str] = set()
    for r in results:
        kept = []
        for f in r.findings:
            fp = finding_fingerprint(r.source, f)
            seen.add(fp)
            if fp in known:
                diff.unchanged += 1
            else:
                kept.append(f)
        diff.new += len(kept)
        r.findings = kept
    rescanned = {r.source for r in results if not r.error}
    diff.gone = sum(1 for fp, src in known.items() if src in rescanned and fp not in seen)
    return diff


RENDERERS: dict[str, Callable[[list[PageResult]], str]] = {
    "text": lambda rs: render(rs) + "\n",
    "json": lambda rs: render_json(rs) + "\n",
    "receipt": render_receipt,
    "csv": render_csv,
    "html": render_html,
    "sarif": render_sarif,
}


# --- Command line ------------------------------------------------------------------------------


def main(
    argv: list[str] | None = None,
    fetcher: Fetcher | None = None,
    sleep: Callable[[float], None] = time.sleep,
    agent_fetch: Callable[[str, str], str] | None = None,
    crawler: Callable[[str, int], tuple[list, list[str]]] | None = None,
    opinion_detectors: dict | None = None,
    langfuse_client: object | None = None,
    css_fetcher: Fetcher | None = None,
    robots_fetcher: Fetcher | None = None,
    pdf_fetcher: Callable[[str], bytes] | None = None,
    header_fetcher: Callable[[str], dict] | None = None,
    otel_tracer: object | None = None,
    image_fetcher: Callable[[str], bytes] | None = None,
    ocr: Callable[[bytes], str] | None = None,
) -> int:
    """Run the command line; return the exit code.

    ``fetcher`` (url -> body text) replaces :func:`fetch` for pages and sitemaps, ``css_fetcher``
    for stylesheets (``--fetch-css``), ``robots_fetcher`` for robots.txt, ``pdf_fetcher`` (url -> bytes) for PDF URLs,
    ``header_fetcher`` (url -> headers) for ``--headers``, and ``sleep`` replaces :func:`time.sleep`, so tests
    run offline and without waiting.
    """
    parser = argparse.ArgumentParser(prog="pagevet", description="Check pages for text aimed at AI models (prompt injection).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("sources", nargs="*", help="file paths, http(s) URLs, or - for stdin")
    parser.add_argument("--format", choices=sorted(RENDERERS), default="text", help="report format (default: text)")
    parser.add_argument("--json", dest="format", action="store_const", const="json", help="same as --format json")
    parser.add_argument("--out", metavar="FILE", help="write the report to FILE instead of stdout")
    parser.add_argument("--sitemap", metavar="URL_OR_FILE", action="append", default=[],
                        help="scan the <loc> URLs of a sitemap.xml or sitemap index (one level deep); repeatable")
    parser.add_argument("--urls", metavar="FILE", action="append", default=[],
                        help="scan the URLs in FILE, one per line (# comments and blank lines skipped); repeatable")
    parser.add_argument("--max-pages", type=int, default=50, metavar="N", help="fetch at most N pages over http(s) (default: 50)")
    parser.add_argument("--delay", type=float, default=0.5, metavar="SECONDS", help="pause between page fetches (default: 0.5)")
    parser.add_argument("--via", choices=("http", "firecrawl"), default="http",
                        help="how to fetch URLs: plain http (default) or your Firecrawl service (rendered HTML; see pagevet.sources)")
    parser.add_argument("--crawl", metavar="URL", action="append", default=[],
                        help="crawl a site through your crawlee-server and scan every captured page; repeatable")
    parser.add_argument("--crawl-mode", choices=("crawl", "page", "sitemap", "map"), default="crawl",
                        help="crawlee-server mode for --crawl: crawl (follow links, default), page (start URL only), sitemap, map")
    parser.add_argument("--compare-agents", action="store_true",
                        help="also fetch each URL as GPTBot, ClaudeBot and PerplexityBot and report content served only to them")
    parser.add_argument("--second-opinion", metavar="NAME", action="append", default=[], choices=("promptguard", "protectai", "jev", "llm", "ollama"),
                        help="attach an optional detector's score to low and medium findings: promptguard (local model), jev or llm (billed); repeatable")
    parser.add_argument("--langfuse", metavar="RUN", nargs="?", const="", default=None,
                        help='record each page in Langfuse as a trace, with RUN as the session (default: a dated name); '
                             'needs LANGFUSE_* keys and pip install "pagevet[langfuse]"')
    parser.add_argument("--include-repetition", action="store_true",
                        help="also report channels that are only one repeated claim (off by default: frequent on ordinary pages)")
    parser.add_argument("--fail-on", choices=SEVERITIES, default="low", metavar="LEVEL",
                        help="exit 1 only for findings at or above LEVEL: low, medium or high (default: low)")
    parser.add_argument("--fetch-css", action="store_true",
                        help="also read each fetched page's own linked stylesheets (same host, up to 5) for hiding rules")
    parser.add_argument("--css-any-host", action="store_true",
                        help="with --fetch-css, also read stylesheets on other hosts (CDNs)")
    parser.add_argument("--ignore-robots", action="store_true",
                        help="fetch pages even where robots.txt disallows them (for your own site)")
    parser.add_argument("--otel", metavar="RUN", nargs="?", const="", default=None,
                        help='also send one OpenTelemetry span per page (OTEL_* settings, pip install "pagevet[otel]")')
    parser.add_argument("--ocr", action="store_true",
                        help='also read text inside each page\'s images (up to 10 per page; pip install "pagevet[ocr]")')
    parser.add_argument("--headers", action="store_true",
                        help="also scan each URL's HTTP response headers (one extra request per page)")
    parser.add_argument("--llms-txt", action="store_true",
                        help="also scan /llms.txt and /llms-full.txt of each site scanned over http(s)")
    parser.add_argument("--baseline", metavar="FILE",
                        help="an earlier --format json report; keep only findings that are not in it")
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:  # bare `pagevet`: the full help, with the usual usage-error exit code
        parser.print_help(sys.stderr)
        parser.exit(2)
    args = parser.parse_args(argv)
    injected_fetcher = fetcher is not None
    from pagevet.config import load_env_file

    load_env_file()
    if not (args.sources or args.sitemap or args.urls or args.crawl):
        parser.error("give at least one source, --sitemap, --urls or --crawl")
    if args.css_any_host and not args.fetch_css:
        parser.error("--css-any-host needs --fetch-css")
    if args.max_pages < 0 or args.delay < 0:
        parser.error("--max-pages and --delay must not be negative")
    known: dict[str, str] | None = None
    if args.baseline:
        try:
            known = load_baseline(args.baseline)
        except (OSError, ValueError) as exc:
            parser.error(f"--baseline: {exc}")

    from pagevet import sources as page_sources

    css_cache: dict[str, str] = {}
    css_get = css_fetcher or (lambda u: fetch(u, timeout=10.0, max_bytes=MAX_STYLESHEET_BYTES))

    def cached_css(url: str) -> str:  # a site's pages usually share stylesheets: fetch each once per run
        if url not in css_cache:
            css_cache[url] = css_get(url)
        return css_cache[url]

    def page_css(url: str, body: str) -> str:
        if not args.fetch_css or not looks_like_html(body):
            return ""
        css, notes = fetch_stylesheets(body, url, cached_css, any_host=args.css_any_host)
        for note in notes:
            sys.stderr.write(f"pagevet: {url}: {note}\n")
        return css

    results: list[PageResult] = []
    if args.via == "firecrawl" and fetcher is None:
        try:
            fetcher = page_sources.firecrawl_fetcher()
        except page_sources.SourceError as exc:
            parser.error(str(exc))
    for start in args.crawl:
        try:
            pages, notes = (crawler(start, args.max_pages) if crawler
                            else page_sources.crawl(start, args.max_pages, mode=args.crawl_mode))
            for page in pages:
                result = scan_text(page.url, page.body, args.include_repetition, page_css(page.url, page.body))
                result.evidence = page.evidence
                results.append(result)
            for note in notes:
                sys.stderr.write(f"pagevet: {start}: {note}\n")
        except Exception as exc:  # report and keep going
            results.append(PageResult(start, [], _err(exc)))
    sources: list[str] = list(args.sources)
    for sm in args.sitemap:
        try:
            urls, errs = sitemap_urls(sm, fetcher)
            sources.extend(urls)
            results.extend(errs)
        except Exception as exc:  # report and keep going
            results.append(PageResult(sm, [], _err(exc)))
    for path in args.urls:
        try:
            sources.extend(read_url_list(path))
        except Exception as exc:  # report and keep going
            results.append(PageResult(path, [], _err(exc)))
    sources = list(dict.fromkeys(sources))  # drop duplicates, keep order

    fetched = skipped = 0
    # robots.txt is read over plain HTTP (also with --via firecrawl). A caller that injects its own page
    # fetcher without a robots_fetcher (tests, library use) gets no robots check.
    robots = Robots(robots_fetcher) if robots_fetcher or not injected_fetcher else None
    for src in sources:
        if _is_url(src):
            if fetched >= args.max_pages:
                skipped += 1
                continue
            if fetched and args.delay:
                sleep(args.delay)
            fetched += 1
        if _is_url(src) and robots and not args.ignore_robots and not robots.allowed(src):
            results.append(PageResult(src, [], "robots.txt disallows this page for pagevet; --ignore-robots to scan it anyway"))
            continue
        try:
            if is_pdf_source(src):
                data = (pdf_fetcher or fetch_bytes)(src) if _is_url(src) else Path(src).read_bytes()
                results.append(scan_pdf(src, data, args.include_repetition))
                continue
            body = read_source(src, fetcher)
            page = scan_text(src, body, args.include_repetition, page_css(src, body) if _is_url(src) else "")
            page.evidence = read_evidence(src, body, args.via)
            if args.compare_agents and _is_url(src):
                page.findings.extend(compare_agents(src, agent_fetch or (lambda u, ua: fetch(u, user_agent=ua))))
            if args.ocr and _is_url(src) and looks_like_html(body):
                text, notes = ocr_text(image_sources(body, src), image_fetcher or (lambda u: fetch_bytes(u, timeout=15.0, max_bytes=MAX_IMAGE_BYTES)),
                                       ocr or default_ocr)
                for note in notes:
                    sys.stderr.write(f"pagevet: {src}: image {note}\n")
                page.findings.extend(scan_channels(src, {"text in images": text}, args.include_repetition).findings)
            if args.headers and _is_url(src):
                try:
                    text = header_text((header_fetcher or fetch_headers)(src))
                    page.findings.extend(scan_channels(src, {"HTTP response headers": text}, args.include_repetition).findings)
                except Exception as exc:  # the page result stands without its headers
                    sys.stderr.write(f"pagevet: {src}: headers not read: {_err(exc)}\n")
            results.append(page)
        except Exception as exc:  # report and keep going
            results.append(PageResult(src, [], _err(exc)))
    if args.llms_txt:
        roots = list(dict.fromkeys(site_root(r.source) for r in results if _is_url(r.source) and not r.error))
        for root in roots:
            for name in LLMS_FILES:
                url = f"{root}/{name}"
                if robots and not args.ignore_robots and not robots.allowed(url):
                    sys.stderr.write(f"pagevet: {url}: robots.txt disallows it; not scanned\n")
                    continue
                try:
                    body = fetcher(url) if fetcher else fetch(url, timeout=10.0, max_bytes=MAX_LLMS_BYTES)
                except Exception as exc:  # most sites have none; not an error in the report
                    sys.stderr.write(f"pagevet: {url}: not read ({_err(exc)})\n")
                    continue
                if not body.strip() or looks_like_html(body):
                    sys.stderr.write(f"pagevet: {url}: no llms.txt (empty or an HTML page)\n")
                    continue
                results.append(scan_channels(url, {"llms.txt": body}, args.include_repetition))
    if skipped:
        sys.stderr.write(f"pagevet: --max-pages {args.max_pages} reached; {skipped} URL(s) not scanned\n")

    for name in args.second_opinion:
        try:
            add_opinions(results, (opinion_detectors or {}).get(name) or build_detector(name))
        except Exception as exc:  # an optional layer must never lose the scan
            sys.stderr.write(f"pagevet: second opinion {name} skipped: {_err(exc)}\n")

    if known is not None:
        diff = apply_baseline(results, known)
        sys.stderr.write(f"pagevet: baseline {args.baseline}: {diff.new} new, {diff.unchanged} unchanged, "
                         f"{diff.gone} no longer found\n")
    if args.langfuse is not None:
        try:
            import time as _time

            from pagevet import __version__ as version
            from pagevet.tracing import record_scan

            run = args.langfuse or f"pagevet-{_time.strftime('%Y%m%d-%H%M%S')}"
            sent = record_scan(results, run, version, langfuse_client)
            sys.stderr.write(f"pagevet: {sent} page(s) recorded in Langfuse, session {run}\n")
        except Exception as exc:  # recording must never lose the scan
            sys.stderr.write(f"pagevet: Langfuse recording skipped: {_err(exc)}\n")
    if args.otel is not None:
        try:
            import time as _time

            from pagevet import __version__ as version
            from pagevet.tracing import record_otel

            run = args.otel or f"pagevet-{_time.strftime('%Y%m%d-%H%M%S')}"
            sent = record_otel(results, run, version, otel_tracer)
            sys.stderr.write(f"pagevet: {sent} page span(s) sent over OpenTelemetry, run {run}\n")
        except Exception as exc:  # tracing must never lose the scan
            sys.stderr.write(f"pagevet: OpenTelemetry skipped: {_err(exc)}\n")
    if args.format == "sarif":
        report = render_sarif(results, baseline=known is not None)
    else:
        report = RENDERERS[args.format](results)
    if args.out:
        try:
            Path(args.out).write_text(report, encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"pagevet: cannot write {args.out}: {exc}\n")
            return 2
    else:
        sys.stdout.write(report)
    failing = any(at_least(r.findings, args.fail_on) for r in results)
    if any(r.error for r in results) and not failing:
        return 2
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
