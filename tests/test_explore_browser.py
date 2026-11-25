"""The explorer in a real browser: displayed counts equal Python's, CSP holds, URL state round-trips,
tampered or unknown data fails closed, and page data renders as text. Offline (file:// only).

Needs the ``browser`` dependency group (``uv sync --group browser``) and an installed Chrome or
Chromium (``PAGEVET_CHROME``, else /usr/bin/google-chrome or Playwright's own). Skipped otherwise.
"""
import glob
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlencode

import pytest

from pagevet import explore

sync_api = pytest.importorskip("playwright.sync_api")
CHROME = os.environ.get("PAGEVET_CHROME") or shutil.which("google-chrome") or shutil.which("chromium") or ""
FIELD = sorted(glob.glob("docs/bench/*-field-*"))
FILTERS = [
    ("field", {}, ""),
    ("field", {"read": ["read"]}, ""),
    ("field", {"study": ["home solar panel pages"], "refused": ["0"]}, ""),
    ("field", {"GPTBot": ["served"], "differs": ["no", "yes"]}, ""),
    ("field", {}, "shop"),
    ("pages", {"language": ["Polish", "English"]}, ""),
    ("pages", {"severity": ["low"]}, ""),
    ("bench", {"set": ["held-out 2 (new phrasings)"], "result": ["caught"]}, ""),
    ("bench", {"language": ["Russian", "Chinese"]}, ""),
    ("field", {"group": ["training not served"], "language": ["not recorded in this study"]}, ""),
    ("pages", {"how": ["crawlee-server 2.2.0"], "read": ["read"]}, ""),
]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=CHROME or None, args=["--no-sandbox"])
        except Exception as exc:  # no browser on this machine
            pytest.skip(f"no Chrome or Chromium: {exc}"[:200])
        yield b
        b.close()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    page = explore.explore(FIELD, str(out), "docs/bench", "test123")
    data = explore.build_data([Path(f) for f in FIELD], Path("docs/bench"), "test123")
    return page, data


def open_page(browser, path, fragment=""):
    page = browser.new_page()
    page.errors, page.console_errors = [], []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: m.type in ("error", "warning") and page.console_errors.append(m.text))
    page.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
    page.goto(Path(path).as_uri() + fragment)
    page.wait_for_selector("body[data-state=ready], body[data-state=error]", timeout=20000)
    return page


def fragment(ds, filters, q):
    pairs = [("ds", ds)] + [(f"f.{k}", v) for k in sorted(filters) for v in filters[k]] + ([("q", q)] if q else [])
    return "#" + urlencode(pairs)


def shown_counts(page):
    out = {}
    for key, value, count in page.eval_on_selector_all(
            "#facets label[data-facet]", "els => els.map(e => [e.dataset.facet, e.dataset.value, e.querySelector('.count').dataset.count])"):
        if count != "0":
            out.setdefault(key, {})[value] = int(count)
    return out


@pytest.mark.parametrize("ds,filters,q", FILTERS)
def test_displayed_counts_equal_python(browser, built, ds, filters, q):
    path, data = built
    page = open_page(browser, path, fragment(ds, filters, q))
    assert page.evaluate("document.body.dataset.state") == "ready"
    expected = {k: v for k, v in explore.facet_counts(data["records"], ds, filters, q).items() if v}
    assert shown_counts(page) == expected
    h = explore.headline(data["records"], ds, filters, q)
    if ds == "bench":
        assert int(page.get_attribute("#h-cases", "data-value")) == h["cases"]
        assert int(page.get_attribute("#h-caught", "data-value")) == h["caught"]
    else:
        assert int(page.get_attribute("#h-read", "data-value")) == h["read"]
        assert int(page.get_attribute("#h-flagged", "data-value")) == h["flagged"]
        if ds == "field":
            assert int(page.get_attribute("#h-refusing", "data-value")) == h["refusing"]
    assert page.errors == [] and page.console_errors == []  # includes CSP violations, which Chrome logs as errors
    page.close()


def test_no_filter_shows_published_figures(browser, built):
    # The published figures are tied to the README and FIELD-STUDIES.md in test_explore.py; here the page must show
    # the same headline, computed from the committed data, so adding a study never needs a new literal.
    h = explore.headline(built[1]["records"], "field", {}, "")
    page = open_page(browser, built[0])
    assert int(page.get_attribute("#h-read", "data-value")) == h["read"]
    assert int(page.get_attribute("#h-flagged", "data-value")) == h["flagged"]  # 4 since 1.1.0 (test_explore.py ties it to the data)
    assert int(page.get_attribute("#h-refusing", "data-value")) == h["refusing"]
    page.close()


def test_url_state_round_trips(browser, built):
    page = open_page(browser, built[0])
    page.click('#facets label[data-facet="study"][data-value="home solar panel pages"] input')
    page.fill("#q", "solar")
    page.wait_for_function("location.hash.includes('q=solar')")
    hash_, counts = page.evaluate("location.hash"), shown_counts(page)
    page.close()
    again = open_page(browser, built[0], hash_)
    assert again.is_checked('#facets label[data-facet="study"][data-value="home solar panel pages"] input')
    assert again.input_value("#q") == "solar" and shown_counts(again) == counts
    again.close()


def test_tampered_data_fails_closed(browser, built, tmp_path):
    html = built[0].read_text()
    tampered = tmp_path / "tampered.html"
    tampered.write_text(html.replace('"schema_version":1', '"schema_version":1 ', 1))
    page = open_page(browser, tampered)
    assert page.evaluate("document.body.dataset.state") == "error" and "does not match its SHA-256" in page.text_content("#error")
    assert page.query_selector("#headline") is None
    page.close()


def test_unknown_schema_fails_closed(browser, built, tmp_path):
    data = dict(built[1], schema_version=99)
    path = tmp_path / "s.html"
    path.write_text(explore.render_page(data))
    page = open_page(browser, path)
    assert page.evaluate("document.body.dataset.state") == "error" and "Unknown schema_version" in page.text_content("#error")
    page.close()


def test_planted_markup_renders_as_text(browser, built, tmp_path):
    data = json.loads(json.dumps(built[1]))
    evil = "<script>window.__pwned=1</script><img src=x onerror=window.__pwned=2>"
    data["records"].insert(0, {"id": "x/1", "ds": "field", "url": "https://evil.example/" + evil, "domain": "evil.example", "title": evil,
                               "f": {"study": [evil], "read": ["read"], "severity": ["none"], "refused": ["0"], "differs": ["no"]},
                               "d": {"status": evil, "how": "", "findings": [], "crawlers": [], "recheck": evil, "hashes": ""}})
    path = tmp_path / "x.html"
    path.write_text(explore.render_page(data))
    page = open_page(browser, path, "#" + urlencode([("ds", "field"), ("id", "x/1")]))
    assert page.evaluate("window.__pwned") is None
    assert evil in page.text_content("#results") and evil in page.text_content("#drawer")
    assert page.query_selector("#results img") is None
    page.close()


def test_hash_in_page_matches_python(built):
    html = built[0].read_text()
    payload = re.search(r'<script id="pv-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert hashlib.sha256(payload.encode()).hexdigest() in html


def test_compare_view_highlights_differences(browser, built):
    page = open_page(browser, built[0], "#" + urlencode([("ds", "field"), ("view", "compare"), ("ca", "2026-11-23-field-crm"), ("cb", "2026-11-23-field-home-solar"), ("pair", "3")]))
    text = page.text_content("#compare")
    assert "small-business CRM software pages" in text and "home solar panel pages" in text
    assert page.locator("#compare table").first.locator("tr.diff").count() >= 3  # e.g. scanned 48 vs 43
    assert "0.23.0" in text and "0.24.0" in text and "rated the same by both versions" in text
    assert page.is_hidden("#layout") and page.errors == [] and page.console_errors == []
    page.close()


def test_about_and_wording(browser, built):
    page = open_page(browser, built[0], "#ds=field&view=about")
    about = page.text_content("#about")
    assert "Not read is not clean" in about and "a site's choice" in about and "cloak" not in about.lower()
    page.close()


def test_drawer_shows_evidence_and_recheck_command(browser, built):
    data = built[1]
    rec = next(r for r in data["records"] if r["ds"] == "field" and r["f"]["GPTBot"][0].startswith("not served"))
    page = open_page(browser, built[0], "#" + urlencode([("ds", "field"), ("id", rec["id"])]))
    drawer = page.text_content("#drawer")
    assert rec["url"] in drawer and "pagevet --compare-agents --fetch-css" in drawer and "pagevet-access" in drawer
    assert "not served" in drawer and "Re-check this page" in drawer
    page.keyboard.press("Escape")
    page.wait_for_function("!location.hash.includes('id=')")
    assert page.is_hidden("#drawer")
    unread = next(r for r in data["records"] if r["ds"] == "field" and r["f"]["read"] != ["read"])
    page2 = open_page(browser, built[0], "#" + urlencode([("ds", "field"), ("id", unread["id"])]))
    assert "not counted as clean" in page2.text_content("#drawer")
    page.close()
    page2.close()


def test_reproduce_and_footer(browser, built):
    page = open_page(browser, built[0], "#" + urlencode([("ds", "field"), ("f.study", "home solar panel pages")]))
    cmd = page.text_content("#reproduce-cmd")
    assert "pagevet-study report docs/bench/2026-11-23-field-home-solar" in cmd and "pagevet-study explore" in cmd
    assert "brake" not in cmd.split("compare")[0]
    footer = page.text_content("#footer")
    data = built[1]
    assert f"PageVet {data['provenance']['pagevet']}" in footer and "commit test123" in footer
    assert f"{data['provenance']['records']} records" in footer and "verified in this page" in footer
    page.close()


def test_show_more_pages_the_table_but_counts_cover_everything(browser, built):
    page = open_page(browser, built[0], "#ds=pages")
    assert page.locator("#results tbody tr").count() == 100
    page.click("#results button.more")
    assert page.locator("#results tbody tr").count() == 200
    assert page.get_attribute("#h-pages", "data-value") == str(explore.headline(built[1]["records"], "pages")["pages"])
    page.close()
