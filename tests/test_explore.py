"""The field-study explorer: data, shared counting rules, determinism, privacy, published figures. Offline."""
import glob
import json
import re
from pathlib import Path

import pytest

from pagevet import explore
from pagevet.study import compare, summarize

BENCH = Path("docs/bench")
FIELD = sorted(glob.glob("docs/bench/*-field-*"))


@pytest.fixture(scope="module")
def data():
    return explore.build_data([Path(f) for f in FIELD], BENCH, "test")


def test_two_builds_are_byte_identical(tmp_path):
    a = explore.explore(FIELD, str(tmp_path / "a"), str(BENCH), "abc1234").read_bytes()
    b = explore.explore(FIELD, str(tmp_path / "b"), str(BENCH), "abc1234").read_bytes()
    assert a == b
    assert len(a) < 2_000_000


def test_page_is_self_contained_with_strict_csp(tmp_path):
    html = explore.explore(FIELD, str(tmp_path), str(BENCH), "abc1234").read_text()
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
    assert "default-src 'none'" in csp and "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp
    assert re.search(r"script-src 'sha256-[A-Za-z0-9+/=]+'", csp)
    assert html.count("<script") == 2  # the JSON data block and the one inline script
    code = re.sub(r'<script id="pv-data" type="application/json">.*?</script>', "", html, flags=re.S)
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=|https?://", code)  # nothing loaded from anywhere
    assert "innerHTML" not in code and "eval(" not in code


def test_embedded_hash_matches_data(tmp_path):
    import hashlib

    html = explore.explore(FIELD, str(tmp_path), str(BENCH), "x").read_text()
    payload = re.search(r'<script id="pv-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert re.search(r'name="pv-data-sha256" content="([0-9a-f]{64})"', html).group(1) == hashlib.sha256(payload.encode()).hexdigest()
    assert "<" not in payload  # escaped, so no data can close the block
    assert json.loads(payload)["schema_version"] == explore.SCHEMA_VERSION


def test_private_sample_never_appears(tmp_path):
    private = explore.private_urls(BENCH)
    html = explore.explore(FIELD, str(tmp_path), str(BENCH), "x").read_text()
    payload = re.search(r'<script id="pv-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    urls = json.loads(payload)
    text = json.dumps(urls)
    assert not [u for u in private if u in text]
    name = explore.private_dir(BENCH)
    assert not name or name not in html
    if (BENCH / name / "urls.txt").is_file() and name:
        assert private  # in the private repo the exclusion list must actually be read


def test_headline_equals_published_field_figures(data):
    h = explore.headline(data["records"], "field")
    per = [summarize(json.loads((Path(f) / "results.json").read_text())) for f in FIELD]
    assert h["read"] == sum(s["read"] for s in per) == 273
    # 1.1.0's AI share-button study: 1 high (an alt-text false alarm) and 3 low (articles quoting the technique, a footer link)
    assert h["flagged"] == sum(sum(s["pages_with_findings"].values()) for s in per) == 4
    assert h["refusing"] == sum(s["refused_any"] for s in per)
    assert h["pages"] == sum(s["scanned"] for s in per) and h["not_read"] == h["pages"] - h["read"]


def test_prose_cannot_drift_from_the_data(data):
    assert Path("docs/bench/FIELD-STUDIES.md").read_text() == compare(FIELD)
    shares = [round(100 * s["refused_any"] / s["read"]) for s in data["studies"]]
    read = sum(s["read"] for s in data["studies"])
    readme = Path("README.md").read_text()
    assert f"no deliberate hidden instructions on any of {read} pages read" in readme
    assert f"but {min(shares)}–{max(shares)}% of readable pages refuse at least one AI crawler" in readme


def test_unread_pages_are_never_clean(data):
    for ds in ("field", "pages"):
        rows = [r for r in data["records"] if r["ds"] == ds]
        unread = [r for r in rows if r["f"]["read"] != ["read"]]
        assert unread, ds
        assert all(r["f"]["severity"] == ["not read"] for r in unread)
        h = explore.headline(rows, ds)
        assert h["read"] + h["not_read"] == len(rows) and h["read"] == len(rows) - len(unread)
    unread_field = [r for r in data["records"] if r["ds"] == "field" and r["f"]["read"] != ["read"]]
    assert all(r["f"]["refused"] == ["not tested"] and r["f"]["differs"] == ["not tested"] for r in unread_field)


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


@pytest.mark.parametrize("ds,filters,q", FILTERS)
def test_counts_are_disjunctive(data, ds, filters, q):
    counts = explore.facet_counts(data["records"], ds, filters, q)
    for key, wanted in filters.items():
        # picking values in a facet leaves that facet's own counts as they were without it
        others = {k: v for k, v in filters.items() if k != key}
        assert counts[key] == explore.facet_counts(data["records"], ds, others, q)[key]
        shown = sum(counts[key].get(v, 0) for v in wanted)
        assert shown == len([r for r in data["records"] if r["ds"] == ds and explore.matches(r, filters, q)]) or len(wanted) > 1


def test_wilson_interval():
    assert explore.wilson(0, 213)[0] == 0 and 0.017 < explore.wilson(0, 213)[1] < 0.018
    lo, hi = explore.wilson(5, 50)
    assert 0.04 < lo < 0.05 and 0.21 < hi < 0.22


def test_cli_writes_the_page(tmp_path):
    from pagevet.study import main

    assert main(["explore", *FIELD, "--out", str(tmp_path), "--commit", "deadbee"]) == 0
    assert "commit" in (tmp_path / "index.html").read_text()
