"""The field-study explorer: one self-contained HTML page over PageVet's committed results.

    pagevet-study explore docs/bench/*-field-* --out site/

Reads the committed study folders, false-alarm sets and evasion cases, normalises them into one
versioned record list, and writes ``site/index.html``: the data embedded as JSON with its SHA-256,
and a small vanilla-JS faceted explorer (no server, no CDN, works offline). The page has a strict
Content-Security-Policy that allows exactly its one inline script and one inline style by hash, and
renders every value with ``textContent``.

The facet definitions and the counting rules live here and are embedded in the page, so the page
and :func:`facet_counts` / :func:`headline` (which the tests use as the reference) apply the same
definitions. The same inputs give byte-identical output.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pagevet import __version__
from pagevet.study import AGENTS, _reason, summarize

SCHEMA_VERSION = 1
EXCERPT = 200
AGENT_GROUP = {"GPTBot": "training", "ClaudeBot": "training", "PerplexityBot": "search"}
GROUP_ORDER = ("search", "fetch on request", "training")  # the field studies tested no fetch-on-request crawler

FACETS: dict[str, list[dict[str, str]]] = {
    "field": [
        {"key": "study", "label": "Study"},
        {"key": "language", "label": "Language"},
        {"key": "date", "label": "Run date"},
        {"key": "version", "label": "PageVet version"},
        {"key": "read", "label": "Read outcome"},
        {"key": "how", "label": "How read"},
        {"key": "severity", "label": "Text aimed at AI (highest severity)"},
        {"key": "category", "label": "Finding category"},
        {"key": "refused", "label": "AI crawlers not served (of 3 tested)"},
        {"key": "group", "label": "Crawler groups with one not served"},
        {"key": "GPTBot", "label": "GPTBot (training)"},
        {"key": "ClaudeBot", "label": "ClaudeBot (training)"},
        {"key": "PerplexityBot", "label": "PerplexityBot (search)"},
        {"key": "differs", "label": "Served different text to an AI crawler"},
        {"key": "robots_rule", "label": "Deciding robots.txt rule"},
        {"key": "llms", "label": "llms.txt"},
        {"key": "noai", "label": "noai signals"},
        {"key": "domain", "label": "Domain"},
    ],
    "pages": [
        {"key": "set", "label": "Page set"},
        {"key": "language", "label": "Language"},
        {"key": "version", "label": "PageVet rules"},
        {"key": "read", "label": "Read outcome"},
        {"key": "how", "label": "How read"},
        {"key": "severity", "label": "Highest severity"},
        {"key": "category", "label": "Finding category"},
        {"key": "domain", "label": "Domain"},
    ],
    "bench": [
        {"key": "set", "label": "Case set"},
        {"key": "language", "label": "Language"},
        {"key": "technique", "label": "Disguise technique"},
        {"key": "intent", "label": "Instruction type"},
        {"key": "expected", "label": "Expected label"},
        {"key": "result", "label": "Caught or missed"},
        {"key": "severity", "label": "Severity"},
    ],
}
DATASET_LABEL = {"field": "Field studies", "pages": "False-alarm pages", "bench": "Benchmark cases"}

PAGE_SETS = [
    # (folder, results file, label, rules version, how read)
    ("2026-11-19-clean-pages", "results-0.5-rules.jsonl", "ordinary homepages", "internal 0.5.0", "plain HTTP"),
    ("2026-11-19-fresh-pages", "results-http-0.6.jsonl", "articles, forums, Q&A (blind check)", "internal 0.6.0", "plain HTTP"),
    ("2026-11-19-intl-pages", "results-http-0.12.jsonl", "Spanish, French, German, Portuguese", "internal 0.12.0", "plain HTTP"),
    ("2026-11-19-it-nl-pages", "results-http-0.19.jsonl", "Italian and Dutch", "internal 0.19.0", "plain HTTP"),
]
TWELVE = ("2026-11-24-pages-12-languages", "twelve languages (internal 0.24.0)")
# Pages plain HTTP could not read, retried through crawlee-server 2.2.0 (docs/bench/2026-11-19-crawlee/). Separate
# records from the plain-HTTP attempt, so filter by set to avoid counting a URL twice.
CRAWLEE_SETS = [
    ("2026-11-19-clean-pages", "results-crawlee-2.2.0.jsonl", "homepages retried through crawlee-server", "internal 0.5.0"),
    ("2026-11-19-fresh-pages", "results-crawlee-2.2.0.jsonl", "articles retried through crawlee-server", "internal 0.6.0"),
]
# Two PageVet versions on identical saved bytes: (folder, left file, right file, left label, right label)
VERSION_PAIRS = [
    ("2026-11-19-intl-pages", "saved-pages-0.11-rules.jsonl", "saved-pages-0.12-rules.jsonl", "internal 0.11.0", "internal 0.12.0"),
    ("2026-11-19-it-nl-pages", "saved-pages-0.18-rules.jsonl", "saved-pages-0.19-rules.jsonl", "internal 0.18.0", "internal 0.19.0"),
    ("2026-11-19-clean-pages", "results-0.4-rules.jsonl", "results-0.5-rules.jsonl", "internal 0.4.0", "internal 0.5.0"),
    ("2026-11-24-pages-12-languages", "results-0.23.0.json", "results-0.24.0.json", "internal 0.23.0", "internal 0.24.0"),
]
FEED_LANG = {"elpais.com": "es", "lemonde.fr": "fr", "tagesschau.de": "de", "folha.uol.com.br": "pt", "corriere.it": "it", "nos.nl": "nl"}
LANG_NAME = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "it": "Italian", "nl": "Dutch",
             "pl": "Polish", "sv": "Swedish", "ru": "Russian", "ja": "Japanese", "zh": "Chinese"}
SEVERITY_ORDER = ("none", "low", "medium", "high")


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def _short(text: str, n: int = EXCERPT) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _top(findings: list[dict]) -> str:
    sev = [f.get("severity") for f in findings if f.get("severity") in SEVERITY_ORDER]
    return max(sev, key=SEVERITY_ORDER.index) if sev else "none"


def _quote(url: str) -> str:
    return "'" + url.replace("'", "'\\''") + "'"


def private_dir(bench: Path) -> str:
    """The privately supplied sample's folder name, as release/public_copy.py names it ("" in the public copy,
    which has neither that script nor the folder)."""
    script = bench.resolve().parent.parent / "release" / "public_copy.py"
    if not script.is_file():
        return ""
    m = re.search(r'^SAMPLE_DIR = "docs/bench/([^"]+)"', script.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def private_urls(bench: Path) -> set[str]:
    """URLs of the privately supplied sample, never shown (empty in the public copy, where the folder is dropped)."""
    name = private_dir(bench)
    path = bench / name / "urls.txt" if name else None
    if not path or not path.is_file():
        return set()
    return {ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")}


# --- loaders --------------------------------------------------------------------------------------

def load_field(folders: list[Path], private: set[str], skip_dir: str = "") -> tuple[list[dict], list[dict]]:
    records, studies = [], []
    for base in sorted(folders, key=lambda p: p.name):
        if (skip_dir and base.name == skip_dir) or not (base / "study.json").is_file() or not (base / "results.json").is_file():
            continue
        meta = json.loads((base / "study.json").read_text(encoding="utf-8"))
        results = [r for r in json.loads((base / "results.json").read_text(encoding="utf-8")) if r["source"] not in private]
        s = summarize(results)
        version = re.sub(r"\s*\(.*\)$", "", str(meta.get("version", ""))).removesuffix(" development") or "unknown"
        studies.append({"folder": base.name, "topic": meta["topic"], "date": meta["date"], "version": version,
                        "scanned": s["scanned"], "read": s["read"], "unread": s["unread"], "found": s["pages_with_findings"],
                        "refused_any": s["refused_any"], "refused_all": s["refused_all"],
                        "refusals": {a: sum(v.values()) for a, v in s["refusals"].items()}, "differs": len(s["content_differs"])})
        for i, r in enumerate(results):
            url = r["source"]
            read = not r.get("error")
            own = [f for f in r["findings"] if not f["channel"].startswith("served to ")]
            agents: dict[str, str] = {}
            evidence = []
            differs = "not tested"
            if read:
                differs = "no"
                for a in AGENTS:
                    agents[a] = "served"
                for f in r["findings"]:
                    if not f["channel"].startswith("served to "):
                        continue
                    a = f["channel"].removeprefix("served to ")
                    if "fetch_differs" in f["kinds"]:
                        agents[a] = f"not served ({_reason(f['excerpt'])})"
                    elif "content_differs" in f["kinds"] or "cloaked_instruction" in f["kinds"]:
                        if agents.get(a) == "served":
                            agents[a] = "served different text"
                        differs = "yes"
                    evidence.append({"what": f"{a}: " + ("not served" if "fetch_differs" in f["kinds"] else "served different text"),
                                     "where": f["channel"], "quote": _short(f["excerpt"], 140)})
            refused = sum(v.startswith("not served") for v in agents.values())
            groups = sorted({AGENT_GROUP[a] for a, v in agents.items() if v.startswith("not served")}, key=GROUP_ORDER.index)
            sev = _top(own) if read else "not read"
            records.append({
                "id": f"field/{base.name}/{i}", "ds": "field", "url": url, "domain": _domain(url), "title": "",
                "f": {
                    "study": [meta["topic"]], "language": [meta.get("language", "not recorded in this study")], "date": [meta["date"]], "version": [version], "domain": [_domain(url)],
                    "read": ["read" if read else _reason(r["error"])], "how": ["plain HTTP"],
                    "severity": [sev], "category": sorted({k for f in own for k in f["kinds"]}) or (["none"] if read else ["not read"]),
                    "refused": [("all 3" if refused == 3 else str(refused)) if read else "not tested"],
                    "group": [f"{g} not served" for g in groups] or (["all tested groups served"] if read else ["not tested"]),
                    **{a: [agents.get(a, "not tested (page not read)")] for a in AGENTS},
                    "differs": [differs],
                    "robots_rule": ["not recorded in this study"], "llms": ["not tested in this study"], "noai": ["not tested in this study"],
                },
                "d": {
                    "status": "read (HTTP 200)" if read else _short(r["error"], 160),
                    "how": "plain HTTP, robots.txt respected, linked stylesheets read; compared with GPTBot, ClaudeBot and PerplexityBot user agents",
                    "findings": [{"severity": f["severity"], "where": f["channel"], "kinds": f["kinds"], "quote": _short(f["excerpt"]),
                                  "reason": f.get("advice", "")} for f in own],
                    "crawlers": evidence,
                    "recheck": f"pagevet --compare-agents --fetch-css {_quote(url)}\npagevet-access {_quote(url)}",
                    "hashes": "",
                },
            })
    return records, studies


def _crawlee_reason(text: str) -> str:
    """crawlee-server's refusal wording mapped onto the same outcome labels as plain HTTP."""
    if "robotstxt" in (text or "").lower().replace(".", ""):
        return "robots.txt disallows PageVet"
    m = re.search(r"\b([1-5]\d\d)\b", text or "")
    if m:
        return f"HTTP {m.group(1)}"
    return _reason(text or "error")


def _lang(url: str, default: str) -> str:
    host = _domain(url)
    m = re.match(r"([a-z]{2})\.wikipedia\.org$", host)
    if m:
        return m.group(1)
    for suffix, lang in FEED_LANG.items():
        if host.endswith(suffix):
            return lang
    return default


def _page_record(set_label: str, folder: str, i: int, url: str, read: bool, outcome: str, findings: list[dict], version: str,
                 how: str, lang: str, sha: str = "") -> dict:
    sev = _top(findings) if read else "not read"
    return {
        "id": f"pages/{folder}/{i}", "ds": "pages", "url": url, "domain": _domain(url), "title": "",
        "f": {"set": [set_label], "language": [LANG_NAME.get(lang, lang)], "version": [version], "read": [outcome], "how": [how],
              "severity": [sev], "category": sorted({k for f in findings for k in f.get("kinds", [])}) or (["none"] if read else ["not read"]),
              "domain": [_domain(url)]},
        "d": {"status": outcome, "how": how,
              "findings": [{"severity": f.get("severity", ""), "where": f.get("channel", ""), "kinds": f.get("kinds", []),
                            "quote": _short(f.get("excerpt", "")), "reason": f.get("advice", "")} for f in findings],
              "crawlers": [], "recheck": f"pagevet {_quote(url)}", "hashes": f"sha256 {sha}" if sha else ""},
    }


def load_pages(bench: Path, private: set[str]) -> tuple[list[dict], list[dict]]:
    records, sets = [], []
    for folder, name, label, version, how in PAGE_SETS:
        path = bench / folder / name
        if not path.is_file():
            continue
        rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        rows = [r for r in rows if r["url"] not in private]
        n_read = 0
        for i, r in enumerate(rows):
            read = r.get("outcome") == "scanned"
            n_read += read
            outcome = "read" if read else ("robots.txt disallows PageVet" if r.get("outcome") == "robots_disallowed" else _reason(r.get("error", "") or "error"))
            records.append(_page_record(label, folder, i, r["url"], read, outcome, r.get("findings", []), version, how,
                                        _lang(r["url"], "en"), r.get("sha256", "")))
        sets.append({"folder": folder, "label": label, "version": version, "pages": len(rows), "read": n_read})
    for folder, name, label, version in CRAWLEE_SETS:
        path = bench / folder / name
        if not path.is_file():
            continue
        rows = [r for r in (json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()) if r["url"] not in private]
        for i, r in enumerate(rows):
            read = r.get("outcome") == "scanned"
            outcome = "read" if read else _crawlee_reason(r.get("reason", "") or r.get("error", ""))
            rec = _page_record(label, folder + "/crawlee", i, r["url"], read, outcome, r.get("findings", []), version,
                               "crawlee-server 2.2.0", _lang(r["url"], "en"), r.get("sha256", ""))
            if r.get("capture_id"):
                rec["d"]["hashes"] = f"sha256 {r.get('sha256', '')}; crawlee-server capture {r['capture_id']}; fetched {r.get('fetched_at', '')}"
            rec["d"]["recheck"] = f"pagevet --crawl {_quote(r['url'])} --crawl-mode page"
            records.append(rec)
        sets.append({"folder": folder, "label": label, "version": version, "pages": len(rows), "read": sum(r.get("outcome") == "scanned" for r in rows)})
    path = bench / TWELVE[0] / "results-0.24.0.json"
    if path.is_file():
        rows = [r for r in json.loads(path.read_text(encoding="utf-8"))["pages"] if r["url"] not in private]
        for i, r in enumerate(rows):
            records.append(_page_record(TWELVE[1], TWELVE[0], i, r["url"], r["read"], "read" if r["read"] else (r.get("error") or "not read"),
                                        r.get("findings", []), "internal 0.24.0", "plain HTTP", r["lang"]))
        sets.append({"folder": TWELVE[0], "label": TWELVE[1], "version": "internal 0.24.0", "pages": len(rows), "read": sum(r["read"] for r in rows)})
    return records, sets


def _bench_lang(technique: str) -> str:
    m = re.search(r"\((\w\w)\)$", technique)
    return LANG_NAME.get(m.group(1), m.group(1)) if m else "English"


BENCH_SETS = {"disguise": "development (disguised seeds)", "held-out": "held-out 1 (disguised)", "rewording": "development (reworded)",
              "translation": "development (translated)", "translation-held-out": "held-out 1 (translated)", "held-out-2": "held-out 2 (new phrasings)"}


# The benchmark runs the explorer shows. Public versions restart at 0.1.0, so files are named here, not picked by
# number: internal 0.24.0 has the same patterns as public 0.1.0. A new published run updates these names.
EVASION_RESULTS = ("results-0.24.0.json", "internal 0.24.0")
BIPIA_RESULTS = ("results-0.24.0.json", "internal 0.24.0")


def load_bench(bench: Path) -> tuple[list[dict], dict]:
    records = []
    path = bench / "2026-11-19-evasion" / EVASION_RESULTS[0]
    if path.is_file():
        for i, c in enumerate(json.loads(path.read_text(encoding="utf-8"))["cases"]):
            tech = c["technique"].removeprefix("held-out: ")
            tech = re.sub(r"^(translated|held-out 2) \(\w\w\)$", "none (translation)", tech)
            records.append({
                "id": f"bench/evasion/{i}", "ds": "bench", "url": "", "domain": "", "title": f"{c['seed']} / {c['brand']}",
                "f": {"set": [BENCH_SETS.get(c["group"], c["group"])], "language": [_bench_lang(c["technique"])], "technique": [tech],
                      "intent": [c["seed"]], "expected": ["instruction (should be caught)"], "result": ["caught" if c["caught"] else "missed"],
                      "severity": ["not recorded"]},
                "d": {"status": "caught" if c["caught"] else "missed", "how": c["technique"], "findings": [], "crawlers": [],
                      "recheck": "uv run python docs/bench/evasion_run.py docs/bench/2026-11-19-evasion results.json", "hashes": ""},
            })
    bipia = {}
    bp = bench / "2026-11-19-bipia" / BIPIA_RESULTS[0]
    if bp.is_file():
        d = json.loads(bp.read_text(encoding="utf-8"))
        bipia = {"version": BIPIA_RESULTS[1], "caught": d["catch_rate"]["hits"], "cases": d["catch_rate"]["n"],
                 "false_alarms": d["false_alarm_rate"]["hits"], "clean": d["false_alarm_rate"]["n"], "cases_sha256": d.get("cases_sha256", "")}
    return records, bipia


def load_version_pairs(bench: Path, private: set[str]) -> list[dict]:
    pairs = []
    for folder, left, right, ll, rl in VERSION_PAIRS:
        lp, rp = bench / folder / left, bench / folder / right
        if not lp.is_file() or not rp.is_file():
            continue

        def rows(p: Path) -> dict[str, str]:
            if p.suffix == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))["pages"]
                return {r["url"]: (_top(r["findings"]) if r["read"] else "not read") for r in data}
            out = {}
            for ln in p.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    r = json.loads(ln)
                    out[r["url"]] = _top(r.get("findings", [])) if r.get("outcome", "scanned") == "scanned" else "not read"
            return out

        a, b = rows(lp), rows(rp)
        urls = sorted((set(a) | set(b)) - private)
        pairs.append({"name": f"{folder}: {ll} vs {rl} on identical saved bytes", "left": ll, "right": rl,
                      "rows": [[u, a.get(u, "absent"), b.get(u, "absent")] for u in urls]})
    return pairs


# --- the shared rules: counts and headline --------------------------------------------------------

def matches(record: dict, filters: dict[str, list[str]], text: str = "", skip: str | None = None) -> bool:
    """Whether ``record`` passes every facet filter except ``skip``, and the free-text filter."""
    for key, wanted in filters.items():
        if key == skip or not wanted:
            continue
        if not set(record["f"].get(key, [])) & set(wanted):
            return False
    if text:
        hay = " ".join((record.get("url", ""), record.get("domain", ""), record.get("title", ""))).lower()
        if text.lower() not in hay:
            return False
    return True


def facet_counts(records: list[dict], ds: str, filters: dict[str, list[str]], text: str = "") -> dict[str, dict[str, int]]:
    """Disjunctive counts: each facet counts over the records that pass every *other* facet's filter."""
    out: dict[str, dict[str, int]] = {}
    pool = [r for r in records if r["ds"] == ds]
    for facet in FACETS[ds]:
        key = facet["key"]
        counts: dict[str, int] = {}
        for r in pool:
            if matches(r, filters, text, skip=key):
                for v in set(r["f"].get(key, [])):
                    counts[v] = counts.get(v, 0) + 1
        out[key] = counts
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def headline(records: list[dict], ds: str, filters: dict[str, list[str]] | None = None, text: str = "") -> dict[str, Any]:
    """The headline numbers for the filtered records. Unread pages are never counted as clean."""
    rows = [r for r in records if r["ds"] == ds and matches(r, filters or {}, text)]
    if ds == "bench":
        caught = sum(r["f"]["result"] == ["caught"] for r in rows)
        return {"cases": len(rows), "caught": caught, "missed": len(rows) - caught}
    read = [r for r in rows if r["f"]["read"] == ["read"]]
    flagged = [r for r in read if r["f"]["severity"] != ["none"]]
    out: dict[str, Any] = {"pages": len(rows), "read": len(read), "not_read": len(rows) - len(read), "flagged": len(flagged),
                           "flagged_ci": [round(x, 4) for x in wilson(len(flagged), len(read))]}
    if ds == "pages":
        out["medium_or_high"] = sum(r["f"]["severity"][0] in ("medium", "high") for r in read)
    if ds == "field":
        out["refusing"] = sum(r["f"]["refused"] != ["0"] for r in read)
    return out


# --- the page -------------------------------------------------------------------------------------

def _git_commit(repo: Path) -> str:
    import subprocess

    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True,  # noqa: S603, S607
                              timeout=10).stdout.strip()
    except Exception:  # not a checkout (an installed package): say so
        return "unknown"


def build_data(folders: list[Path], bench: Path, commit: str) -> dict[str, Any]:
    private = private_urls(bench)
    field, studies = load_field(folders, private, private_dir(bench))
    pages, sets = load_pages(bench, private)
    cases, bipia = load_bench(bench)
    records = field + pages + cases
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {"pagevet": __version__, "commit": commit, "study_dates": sorted({s["date"] for s in studies}),
                       "records": len(records)},
        "datasets": [{"key": k, "label": DATASET_LABEL[k], "facets": FACETS[k]} for k in ("field", "pages", "bench")],
        "studies": studies, "page_sets": sets, "bipia": bipia, "version_pairs": load_version_pairs(bench, private),
        "records": records,
    }


def _template(name: str) -> str:
    return (Path(__file__).parent / "explore_assets" / name).read_text(encoding="utf-8")


def render_page(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("<", "\\u003c")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    script, style = _template("explore.js"), _template("explore.css")
    sha = lambda s: "sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode()  # noqa: E731
    csp = (f"default-src 'none'; script-src '{sha(script)}'; style-src '{sha(style)}'; img-src data:; "
           "base-uri 'none'; form-action 'none'")
    html = _template("explore.html")
    for key, value in (("CSP", csp), ("DATA_SHA256", digest), ("STYLE", style), ("SCRIPT", script), ("DATA", payload),
                       ("VERSION", __version__)):
        html = html.replace("{{" + key + "}}", value)
    return html


def explore(folders: list[str], out: str, bench: str = "docs/bench", commit: str | None = None) -> Path:
    """Write ``OUT/index.html`` and return its path."""
    bench_dir = Path(bench)
    data = build_data([Path(f) for f in folders], bench_dir, commit if commit is not None else _git_commit(bench_dir))
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    page = dest / "index.html"
    page.write_text(render_page(data), encoding="utf-8")
    return page
