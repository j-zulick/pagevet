"""The AI crawler list as data: the packaged file, the loader's checks, and --crawlers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pagevet import access
from pagevet.access import Crawler, load_crawlers

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_list_loads_with_every_group():
    groups = {c.group for c in access.CRAWLERS}
    assert len(access.CRAWLERS) == 14 and groups == set(access.GROUPS)
    assert access.BY_TOKEN["gptbot"].operator == "OpenAI"
    assert access.BY_TOKEN["google-extended"].user_agent == ""  # control token: never visits on its own


def test_example_file_parses():
    rows = load_crawlers((ROOT / "examples/crawlers/example-ai-crawlers.csv").read_text())
    assert rows == (Crawler("ExampleAIBot", "Example AI Inc.", "search", "Mozilla/5.0 (compatible; ExampleAIBot/1.0; +https://example.com/bot)"),)


@pytest.mark.parametrize("text, message", [
    ("name,operator,group\nX,Y,search\n", "header"),
    ("token,operator,group,user_agent\nBad Token,Y,search,\n", "token"),
    ("token,operator,group,user_agent\nX,Y,shopping,\n", "group"),
    ("token,operator,group,user_agent\nX,,search,\n", "operator"),
    ("token,operator,group,user_agent\nX,Y,search,\nx,Z,fetch,\n", "twice"),
    ("token,operator,group,user_agent\n# only a comment\n", "no rows"),
])
def test_bad_rows_are_refused(text, message):
    with pytest.raises(ValueError, match=message):
        load_crawlers(text)


def test_register_refuses_a_known_token(monkeypatch):
    monkeypatch.setattr(access, "CRAWLERS", access.CRAWLERS)
    monkeypatch.setattr(access, "BY_TOKEN", dict(access.BY_TOKEN))
    with pytest.raises(ValueError, match="already"):
        access.register_crawlers((Crawler("GPTBot", "Someone", "training", ""),))


def test_cli_checks_an_added_crawler(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(access, "CRAWLERS", access.CRAWLERS)
    monkeypatch.setattr(access, "BY_TOKEN", dict(access.BY_TOKEN))
    robots = "User-agent: ExampleAIBot\nDisallow: /\n"
    page = "<html><body><p>Hello</p></body></html>"

    def get(url, ua):
        body = robots if url.endswith("/robots.txt") else page
        return access.Response(200, {}, body)

    crawlers = tmp_path / "mine.csv"
    crawlers.write_text("token,operator,group,user_agent\nExampleAIBot,Example AI Inc.,search,ExampleAIBot/1.0\n")
    code = access.main(["https://example.com/", "--crawlers", str(crawlers), "--format", "json", "--no-probe",
                        "--require", "ExampleAIBot=refused"], get=get)
    report = json.loads(capsys.readouterr().out)["reports"][0]
    row = next(c for c in report["crawlers"] if c["token"] == "ExampleAIBot")
    assert code == 0 and row["robots"] == "disallowed"
