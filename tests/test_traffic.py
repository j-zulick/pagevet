"""AI bot-traffic import (0.3.0): CSV, access logs and OpenSearch exports, classified with PageVet's crawler list."""

import json
from datetime import date
from pathlib import Path

import pytest

from pagevet.access import BROWSER_UA, BY_TOKEN
from pagevet.traffic import Hit, classify, detect_format, load, main, read_access_log, read_csv, read_opensearch, summarize, update_windows

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "examples/traffic"
GPT = BY_TOKEN["gptbot"].user_agent
CLAUDE_USER = BY_TOKEN["claude-user"].user_agent


def test_classify_uses_the_crawler_list():
    assert classify(GPT) == ("ai", "GPTBot")
    assert classify(CLAUDE_USER) == ("ai", "Claude-User")
    assert classify(BY_TOKEN["claudebot"].user_agent) == ("ai", "ClaudeBot")
    assert classify(BY_TOKEN["perplexity-user"].user_agent) == ("ai", "Perplexity-User")
    assert classify(BROWSER_UA) == ("other", "")
    assert classify("") == ("unknown", "") and classify("-") == ("unknown", "")
    assert classify("python-requests/2.32") == ("unknown", "")
    assert classify("ExampleSEOBot/3.1") == ("unknown", "")
    assert classify("gptbot", named=True) == ("ai", "GPTBot")
    assert classify("browser", named=True) == ("other", "")
    assert classify("SomethingElse", named=True) == ("unknown", "")


def test_csv_with_user_agent_drops_ip_and_query():
    text = f'date,url,user_agent,hits,client_ip\n2026-10-01,https://a.example/p?q=secret,"{GPT}",3,192.0.2.7\n'
    hits = list(read_csv(text))
    assert hits == [Hit(date(2026, 10, 1), "https://a.example/p", GPT, 3, False)]
    report = json.dumps(summarize(hits))
    assert "192.0.2.7" not in report and "secret" not in report


def test_csv_with_bot_column_and_default_hits():
    hits = list(read_csv("date,url,bot\n2026-10-01T10:00:00Z,/a,ClaudeBot\n2026-10-02,/a,browser\n"))
    r = summarize(hits)
    assert r["pages"] == [{"url": "/a", "bot": "ClaudeBot", "operator": "Anthropic", "group": "training", "kind": "ai", "hits": 1,
                           "first_seen": "2026-10-01", "last_seen": "2026-10-01"}]
    assert r["total_hits"] == 2 and r["unknown_agent_share"] == 0.0


def test_csv_needs_the_columns():
    with pytest.raises(ValueError):
        list(read_csv("day,page\n1,2\n"))


def test_access_log_combined_format():
    log = (f'203.0.113.9 - - [10/Oct/2026:23:30:00 -0700] "GET /p?x=1 HTTP/1.1" 200 512 "-" "{GPT}"\n'
           f'198.51.100.2 - - [11/Oct/2026:01:00:00 +0000] "GET /p HTTP/1.1" 403 0 "https://ref.example/" "-"\n'
           "garbage line\n")
    hits = list(read_access_log(log))
    assert [h.day for h in hits] == [date(2026, 10, 11), date(2026, 10, 11)]  # converted to UTC
    assert hits[0].url == "/p" and hits[0].agent == GPT and hits[1].agent == "-"
    r = summarize(hits)
    assert r["ai_hits"] == 1 and r["unknown_agent_hits"] == 1 and r["unknown_agent_share"] == 0.5
    assert "203.0.113.9" not in json.dumps(r)


def test_opensearch_search_response_and_ndjson_with_field_mapping():
    search = {"hits": {"hits": [{"_source": {"@timestamp": "2026-10-01T09:00:00Z", "url": {"path": "/a"}, "user_agent": {"original": GPT},
                                             "source": {"ip": "192.0.2.1"}}},
                                {"_source": {"@timestamp": 1790000000000, "url": {"path": "/b"}, "user_agent": {"original": CLAUDE_USER}}}]}}
    hits = list(read_opensearch(json.dumps(search)))
    assert [(h.url, classify(h.agent)[1]) for h in hits] == [("/a", "GPTBot"), ("/b", "Claude-User")]
    nd = json.dumps({"ts": "2026-10-02", "request.path": "/c", "agent": GPT}) + "\n" + json.dumps({"_source": {"ts": "2026-10-03", "request": {"path": "/c"}, "agent": "x"}}) + "\n"
    hits = list(read_opensearch(nd, ts_field="ts", url_field="request.path", ua_field="agent"))
    assert [h.url for h in hits] == ["/c", "/c"] and hits[0].day == date(2026, 10, 2)


def test_detect_format():
    assert detect_format("x.csv", "date,url,bot") == "csv"
    assert detect_format("x.ndjson", '{"a":1}') == "opensearch"
    assert detect_format("access.log", '1.2.3.4 - - [01/Oct/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 1') == "log"


def test_update_windows_count_14_days_each_side():
    d = date(2026, 10, 20)
    hits = [Hit(date(2026, 10, 6), "https://a.example/p", GPT), Hit(date(2026, 10, 19), "/p", GPT, 2),
            Hit(d, "/p", GPT, 3), Hit(date(2026, 11, 2), "/p", GPT), Hit(date(2026, 11, 3), "/p", GPT, 9),
            Hit(date(2026, 10, 21), "/other", GPT, 5), Hit(date(2026, 10, 21), "/p", BROWSER_UA, 7)]
    (u,) = update_windows(hits, [("/p", d)])
    assert (u["ai_hits_before"], u["ai_hits_after"]) == (3, 4)  # Oct 6 and 19 before; Oct 20 and Nov 2 after; Nov 3 is outside
    assert u["by_bot"] == {"GPTBot": {"before": 3, "after": 4}}
    assert u["data_covers_both_windows"] is True
    (short,) = update_windows(hits[1:3], [("/p", d)])
    assert short["data_covers_both_windows"] is False


def test_summary_marks_updates_as_a_signal():
    r = summarize([Hit(date(2026, 10, 1), "/p", GPT)], [("/p", date(2026, 10, 2))])
    assert "signal, not proof" in r["updates_note"] and "faked" in r["note"]


@pytest.mark.parametrize("name,extra", [("hits.csv", {}), ("bots.csv", {}), ("access.log", {}), ("opensearch-search.json", {}),
                                        ("opensearch.ndjson", {"ts_field": "timestamp", "url_field": "request.path", "ua_field": "agent"})])
def test_samples_read(name, extra):
    r = load(str(SAMPLES / name), str(SAMPLES / "updates.csv"), **extra)
    assert r["ai_hits"] > 0 and 0 < r["unknown_agent_share"] < 1
    assert r["updates"][0]["ai_hits_after"] > r["updates"][0]["ai_hits_before"]
    text = json.dumps(r)
    assert "192.0.2." not in text and "198.51.100." not in text and "203.0.113." not in text and "utm_source" not in text


def test_cli_json_and_csv(tmp_path, capsys):
    out = tmp_path / "t.csv"
    assert main([str(SAMPLES / "access.log"), "--format", "csv", "--out", str(out), "--updates", str(SAMPLES / "updates.csv")]) == 0
    text = out.read_text()
    assert text.startswith("url,bot,operator,group,kind,hits,first_seen,last_seen") and "signal, not proof" in text
    assert main([str(SAMPLES / "bots.csv")]) == 0
    assert json.loads(capsys.readouterr().out)["tool"] == "pagevet.traffic"
    assert main([str(tmp_path / "missing.csv")]) == 2


def test_extra_bots_file_classifies_search_engines(tmp_path):
    bots = tmp_path / "bots.csv"
    bots.write_text("token,operator,group,user_agent\n"
                    "Googlebot,Google,search engine,Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)\n"
                    "ExampleAIBot,Example,training,ExampleAIBot/1.0\n"
                    "GPTBot,Someone else,search engine,GPTBot\n")  # already on the built-in list: the built-in row wins
    log = tmp_path / "access.log"
    log.write_text(
        '192.0.2.1 - - [01/Oct/2026:10:00:00 +0000] "GET /a HTTP/1.1" 200 1 "-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"\n'
        '192.0.2.1 - - [01/Oct/2026:10:00:00 +0000] "GET /a HTTP/1.1" 200 1 "-" "ExampleAIBot/1.0"\n'
        f'192.0.2.1 - - [01/Oct/2026:10:00:00 +0000] "GET /a HTTP/1.1" 200 1 "-" "{GPT}"\n')
    plain = load(str(log))
    assert plain["ai_hits"] == 1 and plain["listed_bot_hits"] == 0 and plain["unknown_agent_hits"] == 2
    r = load(str(log), bots=str(bots))
    assert r["ai_hits"] == 2 and r["listed_bot_hits"] == 1 and r["unknown_agent_hits"] == 0
    kinds = {b["bot"]: (b["kind"], b["group"], b["operator"]) for b in r["by_bot"]}
    assert kinds == {"Googlebot": ("listed", "search engine", "Google"), "ExampleAIBot": ("ai", "training", "Example"),
                     "GPTBot": ("ai", "training", "OpenAI")}


def test_bots_file_needs_its_header(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,ua\nx,y\n")
    assert main([str(SAMPLES / "access.log"), "--bots", str(bad)]) == 2


def test_sample_search_bots_file():
    r = load(str(SAMPLES / "access.log"), bots=str(SAMPLES / "search-bots.csv"))
    assert r["listed_bot_hits"] > 0 and {b["group"] for b in r["by_bot"] if b["kind"] == "listed"} == {"search engine"}
    assert r["unknown_agent_share"] < load(str(SAMPLES / "access.log"))["unknown_agent_share"]
