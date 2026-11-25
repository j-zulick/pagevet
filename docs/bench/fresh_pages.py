"""Build a fresh list of article and user-content pages from public feeds, for a false-alarm check.

    uv run python docs/bench/fresh_pages.py urls.txt

Homepages (the 2026-11-19 clean-page list) are mostly navigation and marketing copy. Articles,
forum threads, Q&A pages and issue trackers carry long prose and text written by users, which is
where pattern rules are likeliest to fire by mistake. This script takes the current entries from
public, keyless sources, so the list is not chosen by hand and was not seen while the rules were
written. Run it once and keep the output: the feeds change by the minute.
"""
import json
import sys

import httpx
from defusedxml import ElementTree

UA = "pagevet (page audit for text aimed at AI models)"
client = httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True)


def get(url: str):
    r = client.get(url)
    r.raise_for_status()
    return r


def wikipedia(n=30):
    data = get(f"https://en.wikipedia.org/w/api.php?action=query&list=random&rnnamespace=0&rnlimit={n}&format=json").json()
    return ["https://en.wikipedia.org/wiki/" + p["title"].replace(" ", "_") for p in data["query"]["random"]]


def hacker_news(n=30):
    ids = get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:n]
    return [f"https://news.ycombinator.com/item?id={i}" for i in ids]


def stack_overflow(n=30):
    data = get(f"https://api.stackexchange.com/2.3/questions?order=desc&sort=activity&site=stackoverflow&pagesize={n}").json()
    return [q["link"] for q in data["items"]]


def discourse(base, n=15):
    topics = get(f"{base}/latest.json").json()["topic_list"]["topics"][:n]
    return [f"{base}/t/{t['slug']}/{t['id']}" for t in topics]


def rss(url, n=15):
    root = ElementTree.fromstring(get(url).content)
    return [el.text.strip() for el in root.iter("link") if el.text and el.text.strip().startswith("http")][1:n + 1]


def dev_to(n=30):
    return [a["url"] for a in get(f"https://dev.to/api/articles?per_page={n}").json()]


def github_issues(n=20):
    data = get(f"https://api.github.com/repos/python/cpython/issues?per_page={n}&state=all").json()
    return [i["html_url"] for i in data]


SOURCES = {
    "wikipedia (random articles)": wikipedia,
    "hacker news (front-page threads)": hacker_news,
    "stack overflow (active questions)": stack_overflow,
    "discuss.python.org (latest topics)": lambda: discourse("https://discuss.python.org"),
    "meta.discourse.org (latest topics)": lambda: discourse("https://meta.discourse.org"),
    "bbc news (rss)": lambda: rss("https://feeds.bbci.co.uk/news/rss.xml"),
    "npr (rss)": lambda: rss("https://feeds.npr.org/1001/rss.xml"),
    "the guardian (rss)": lambda: rss("https://www.theguardian.com/world/rss"),
    "dev.to (latest articles)": dev_to,
    "github issues (python/cpython)": github_issues,
}

if __name__ == "__main__":
    urls: list[str] = []
    counts = {}
    for name, fn in SOURCES.items():
        try:
            got = fn()
        except Exception as exc:  # one source failing must not lose the others
            sys.stderr.write(f"{name}: skipped: {type(exc).__name__}: {exc}\n")
            got = []
        counts[name] = len(got)
        urls.extend(got)
    urls = list(dict.fromkeys(urls))
    with open(sys.argv[1], "w") as fh:
        fh.write("\n".join(urls) + "\n")
    sys.stdout.write(json.dumps(counts, indent=1) + f"\n{len(urls)} URLs written to {sys.argv[1]}\n")
