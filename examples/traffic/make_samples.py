"""Write the synthetic traffic samples in this folder. Nothing here comes from a real log.

    uv run python examples/traffic/make_samples.py

Hosts are example.com names, client addresses come from the documentation ranges (RFC 5737), and the hit counts are
drawn from a seeded random generator, so the files are the same on every run. Each file carries a client address on
purpose: PageVet's traffic import never reads it.
"""

import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pagevet.access import BROWSER_UA, BY_TOKEN

HERE = Path(__file__).resolve().parent
SITE = "https://shop.example.com"
PAGES = ["/", "/pricing", "/blog/brake-rotors", "/guides/fitting", "/llms.txt"]
START, DAYS = date(2026, 10, 1), 46  # 1 Oct to 15 Nov 2026
UPDATE = ("/pricing", date(2026, 10, 20))
BOTS = ["GPTBot", "ClaudeBot", "OAI-SearchBot", "PerplexityBot", "ChatGPT-User", "Claude-User"]
OTHER = [BROWSER_UA, BROWSER_UA, "python-requests/2.32.3", "-", "ExampleSEOBot/3.1 (+https://seo.example.net/bot)"]
# Search-engine crawlers for the --bots example (search-bots.csv). The strings follow the published formats; the hits are made up.
SEARCH = [
    ("Googlebot", "Google", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ("bingbot", "Microsoft", "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
    ("DuckDuckBot", "DuckDuckGo", "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)"),
    ("YandexBot", "Yandex", "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"),
]
# The search-bots.csv rows: the crawlers above plus ones that get no made-up hits. Google, Microsoft, Apple and DuckDuckGo
# strings as those operators publish them; Yandex, Baidu and Sogou in their commonly logged form. Kept separate from SEARCH so the generated hits stay the same.
SEARCH_FILE = [
    ("Googlebot", "Google", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/W.X.Y.Z Safari/537.36"),
    ("Googlebot-Image", "Google", "Googlebot-Image/1.0"),
    ("Storebot-Google", "Google", "Mozilla/5.0 (X11; Linux x86_64; Storebot-Google/1.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/W.X.Y.Z Safari/537.36"),
    ("bingbot", "Microsoft", "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
    ("Applebot", "Apple", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)"),
    ("DuckDuckBot", "DuckDuckGo", "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)"),
    ("YandexBot", "Yandex", "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"),
    ("YandexImages", "Yandex", "Mozilla/5.0 (compatible; YandexImages/3.0; +http://yandex.com/bots)"),
    ("Baiduspider", "Baidu", "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)"),
    ("Sogou web spider", "Sogou", "Sogou web spider/4.0(+http://www.sogou.com/docs/help/webmasters.htm#07)"),
]
IPS = [f"192.0.2.{i}" for i in range(1, 20)] + [f"198.51.100.{i}" for i in range(1, 20)] + [f"203.0.113.{i}" for i in range(1, 20)]


def events(rng: random.Random):
    for d in range(DAYS):
        day = START + timedelta(days=d)
        for page in PAGES:
            for bot in BOTS:
                rate = 0.35 if bot.endswith("User") else 0.6
                if page == UPDATE[0] and day >= UPDATE[1]:
                    rate += 0.3  # more visits after the update, so the sample shows the before/after table
                if rng.random() < rate:
                    yield day, page, BY_TOKEN[bot.lower()].user_agent, rng.randint(1, 3)
            for _, _, ua in SEARCH:
                if rng.random() < 0.4:
                    yield day, page, ua, rng.randint(1, 4)
            for ua in OTHER:
                if rng.random() < 0.5:
                    yield day, page, ua, rng.randint(1, 6)


def main() -> None:
    rng = random.Random(20261126)  # noqa: S311 - synthetic sample, not security
    rows = list(events(rng))
    with (HERE / "hits.csv").open("w") as fh:
        fh.write("date,url,user_agent,hits,client_ip\n")
        for day, page, ua, n in rows:
            fh.write(f'{day.isoformat()},{SITE}{page}?utm_source=sample,"{ua}",{n},{rng.choice(IPS)}\n')
    with (HERE / "bots.csv").open("w") as fh:
        fh.write("date,url,bot,hits\n")
        names = {BY_TOKEN[b.lower()].user_agent: b for b in BOTS}
        for day, page, ua, n in rows:
            names.update({sua: token for token, _, sua in SEARCH})
            fh.write(f"{day.isoformat()},{page},{names.get(ua, 'browser' if ua == BROWSER_UA else 'ExampleSEOBot')},{n}\n")
    with (HERE / "access.log").open("w") as fh:
        for day, page, ua, n in rows[::5]:  # every fifth row: the whole period, a smaller file
            for k in range(n):
                t = datetime(day.year, day.month, day.day, 8 + k, rng.randint(0, 59), rng.randint(0, 59))
                fh.write(f'{rng.choice(IPS)} - - [{t:%d/%b/%Y:%H:%M:%S} +0000] "GET {page} HTTP/1.1" 200 {rng.randint(800, 40000)} "-" "{ua}"\n')
    hits = []
    for day, page, ua, n in rows[::12]:
        for k in range(n):
            ts = datetime(day.year, day.month, day.day, 9 + k, 0, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
            hits.append({"_index": "weblogs-2026.10", "_id": f"s{len(hits)}",
                         "_source": {"@timestamp": ts, "url": {"path": page, "domain": "shop.example.com"},
                                     "user_agent": {"original": ua}, "source": {"ip": rng.choice(IPS)}, "http": {"response": {"status_code": 200}}}})
    (HERE / "opensearch-search.json").write_text(json.dumps({"took": 3, "timed_out": False, "hits": {"total": {"value": len(hits)}, "hits": hits}}) + "\n")
    with (HERE / "opensearch.ndjson").open("w") as fh:  # flat dotted field names, as some pipelines write them
        for h in hits[::3]:
            s = h["_source"]
            fh.write(json.dumps({"timestamp": s["@timestamp"], "request.path": s["url"]["path"], "agent": s["user_agent"]["original"],
                                 "client.ip": s["source"]["ip"]}) + "\n")
    with (HERE / "search-bots.csv").open("w") as fh:  # the format of src/pagevet/data/ai_crawlers.csv
        fh.write("token,operator,group,user_agent\n")
        for token, operator, ua in SEARCH_FILE:
            fh.write(f'{token},{operator},search engine,"{ua}"\n')
    (HERE / "updates.csv").write_text(f"url,date\n{UPDATE[0]},{UPDATE[1].isoformat()}\n")


if __name__ == "__main__":
    main()
