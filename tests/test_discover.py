"""Offline tests for pagevet-discover."""

import json

from pagevet.discover import main, searxng_search, write_list


def fake_get(url, params):
    assert url == "https://searx.example/search" and params["format"] == "json"
    q = params["q"]
    return {"results": [{"url": f"https://shop.example/{q}/1"}, {"url": f"https://shop.example/{q}/2"},
                        {"url": "https://news.example/a"}, {"url": "javascript:alert(1)"}]}


def test_searxng_search_keeps_http_urls(monkeypatch):
    monkeypatch.setenv("PAGEVET_SEARXNG_URL", "https://searx.example/")
    assert searxng_search("rotors", 2, fake_get) == ["https://shop.example/rotors/1", "https://shop.example/rotors/2"]


def test_write_list_dedupes_and_caps_per_host(tmp_path):
    out = tmp_path / "urls.txt"
    kept = write_list({"a": ["https://x.example/1", "https://x.example/2", "https://y.example/1"],
                       "b": ["https://x.example/1", "https://z.example/1"]}, str(out), max_per_host=1)
    assert kept == ["https://x.example/1", "https://y.example/1", "https://z.example/1"]
    assert out.read_text().splitlines()[0] == "# query: a"


def test_main_with_searxng_and_from_json(tmp_path, monkeypatch):
    monkeypatch.setenv("PAGEVET_SEARXNG_URL", "https://searx.example")
    out = tmp_path / "urls.txt"
    assert main(["rotors", "pads", "--per-query", "3", "--out", str(out)], get=fake_get) == 0
    lines = [ln for ln in out.read_text().splitlines() if not ln.startswith("#")]
    assert len(lines) == 5 and "https://news.example/a" in lines
    src = tmp_path / "found.json"
    src.write_text(json.dumps({"q": ["https://a.example/", "ftp://b.example/"]}))
    assert main(["--from-json", str(src), "--out", str(out)]) == 0
    assert out.read_text().splitlines()[1:] == ["https://a.example/"]


def test_missing_searxng_url_is_reported(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("PAGEVET_SEARXNG_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["rotors"]) == 2
    assert "PAGEVET_SEARXNG_URL" in capsys.readouterr().err
