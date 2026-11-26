"""pagevet-access: robots.txt per RFC 9309, page signals, probes, requirements. Offline."""
import json

import pytest

from pagevet import access
from pagevet.access import Response, check, failed_requirements, main, parse_requirement, parse_robots, robots_verdict

ROBOTS = """
User-agent: GPTBot
User-agent: CCBot
Disallow: /

User-agent: ClaudeBot
Disallow: /private
Allow: /private/ok$

User-agent: *
Disallow: /*.pdf$
Allow: /
"""


@pytest.mark.parametrize("token,path,allowed", [
    ("GPTBot", "/", False),
    ("ccbot", "/page", False),
    ("ClaudeBot", "/private/x", False),
    ("ClaudeBot", "/private/ok", True),
    ("ClaudeBot", "/private/ok2", False),
    ("PerplexityBot", "/a/b.pdf", False),
    ("PerplexityBot", "/a/b.pdf?x=1", True),
    ("PerplexityBot", "/page", True),
    ("GPTBot", "/robots.txt", True),
])
def test_rfc9309_matching(token, path, allowed):
    assert robots_verdict(parse_robots(ROBOTS), token, path)[0] is allowed


def test_longest_match_and_allow_wins_tie():
    groups = parse_robots("User-agent: *\nDisallow: /a\nAllow: /a\nDisallow: /a/b/c\nAllow: /a/b\n")
    assert robots_verdict(groups, "x", "/a")[0] is True          # tie: allow wins
    assert robots_verdict(groups, "x", "/a/b/c/d")[0] is False   # longest rule decides
    assert robots_verdict(groups, "x", "/a/b/x")[0] is True


def test_empty_disallow_and_no_groups_allow_everything():
    assert robots_verdict(parse_robots("User-agent: *\nDisallow:\n"), "GPTBot", "/x")[0] is True
    assert robots_verdict(parse_robots(""), "GPTBot", "/x")[0] is True


def test_groups_for_the_same_token_are_combined():
    groups = parse_robots("User-agent: GPTBot\nDisallow: /a\n\nUser-agent: gptbot\nDisallow: /b\n")
    assert not robots_verdict(groups, "GPTBot", "/a")[0] and not robots_verdict(groups, "GPTBot", "/b")[0]


def test_percent_encoding_of_unreserved_characters():
    assert robots_verdict(parse_robots("User-agent: *\nDisallow: /a%62c\n"), "x", "/abc")[0] is False


def site(robots=(200, ROBOTS), page=(200, "<html><head><meta name='robots' content='noai, noimageai'></head><body>Hi</body></html>"),
         refuse=(), challenge=(), headers=None, llms=(404, "")):
    calls = []

    def get(url, ua):
        calls.append((url, ua))
        if url.endswith("/robots.txt"):
            return Response(robots[0], {}, robots[1])
        if url.endswith("/llms.txt"):
            return Response(llms[0], {"content-type": "text/plain"}, llms[1])
        if url.endswith("/llms-full.txt"):
            return Response(404, {}, "")
        if any(t in ua for t in refuse):
            return Response(403, {}, "Forbidden")
        if any(t in ua for t in challenge):
            return Response(200, {}, "<title>Just a moment...</title> cf-chl")
        return Response(page[0], headers or {}, page[1])

    return get, calls


def test_check_reports_robots_signals_and_firewall_refusals():
    get, calls = site(refuse=("PerplexityBot",), challenge=("Claude-User",))
    r = check("https://shop.example/page", get)
    by = {c.token: c for c in r.crawlers}
    assert len(r.crawlers) == 20
    assert by["GPTBot"].verdict == "refused by robots.txt" and by["GPTBot"].probe == "not probed"
    assert by["PerplexityBot"].verdict == "refused by server" and "firewall" in by["PerplexityBot"].note
    assert by["Claude-User"].probe == "challenge page"
    assert by["OAI-SearchBot"].verdict == "allowed" and "noai" in by["OAI-SearchBot"].page_signals
    assert by["Google-Extended"].probe == "not probed" and by["Google-Extended"].verdict == "allowed (unverified)"
    assert r.summary()["search"] == "6 of 7 allowed"
    assert not any("GPTBot" in ua for _, ua in calls)  # a crawler robots.txt refuses is never probed


def test_robots_404_allows_and_5xx_disallows():
    get, _ = site(robots=(404, ""))
    assert all(not c.verdict.startswith("refused") for c in check("https://a.example/", get).crawlers)
    get, _ = site(robots=(503, ""))
    r = check("https://a.example/", get)
    assert r.robots_txt == "unreachable" and all(c.verdict == "refused by robots.txt" for c in r.crawlers)


def test_per_crawler_meta_header_and_tdm():
    page = "<html><head><meta name='GPTBot' content='noindex'><meta name='tdm-reservation' content='1'></head></html>"
    get, _ = site(robots=(404, ""), page=(200, page), headers={"x-robots-tag": "claudebot: noai"})
    by = {c.token: c for c in check("https://a.example/", get).crawlers}
    assert "noindex" in by["GPTBot"].page_signals and "tdm-reservation" in by["GPTBot"].page_signals
    assert "noai" in by["ClaudeBot"].page_signals and "noai" not in by["GPTBot"].page_signals


def test_llms_txt():
    get, _ = site(llms=(200, "# Example Shop\n\n> Shoes.\n\n- [Docs](https://a.example/docs)\n"))
    info = check("https://a.example/", get).llms_txt["llms.txt"]
    assert info["present"] and info["title"] == "Example Shop" and info["links"] == 1


def test_requirements():
    get, _ = site()
    r = check("https://a.example/", get)
    assert failed_requirements(r, [("GPTBot", "refused")]) == []
    assert failed_requirements(r, [("search", "allowed")]) == []
    assert len(failed_requirements(r, [("training", "allowed")])) >= 2
    with pytest.raises(ValueError):
        parse_requirement("nobot=allowed")
    with pytest.raises(ValueError):
        parse_requirement("GPTBot=maybe")


def test_cli_formats_and_exit_codes(tmp_path, capsys):
    get, _ = site()
    for fmt in ("text", "json", "csv", "markdown"):
        assert main(["https://a.example/", "--format", fmt, "--no-probe"], get=get) == 0
    out = capsys.readouterr().out
    assert "GPTBot" in out
    path = tmp_path / "r.json"
    assert main(["https://a.example/", "--format", "json", "--out", str(path)], get=get) == 0
    assert json.loads(path.read_text())["reports"][0]["summary"]["training"]
    assert main(["https://a.example/", "--require", "GPTBot=allowed"], get=get) == 1
    assert main(["https://a.example/", "--require", "bad"], get=get) == 2
    assert main(["https://a.example/", "--crawler", "NoSuchBot"], get=get) == 2
    assert main([], get=get) == 2


def test_crawler_list_is_complete():
    assert len(access.CRAWLERS) == 20 and {c.group for c in access.CRAWLERS} == set(access.GROUPS)
