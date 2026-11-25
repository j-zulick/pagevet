"""False-alarm check for 0.24.0 on real pages in all twelve languages, and scan time against 0.23.0.

    uv run python docs/bench/pages_12_languages.py urls  OUT_DIR          # build urls.txt (random, keyless sources)
    uv run python docs/bench/pages_12_languages.py fetch OUT_DIR PAGES    # fetch each page once (robots.txt respected)
    uv run python docs/bench/pages_12_languages.py scan  PAGES OUT.json   # scan the saved pages, with timings

Random Wikipedia articles (20 per language) plus the current entries of one public news feed per
language, so the list is not chosen by hand. Pages are fetched once with plain HTTP and saved
(PAGES, a gzipped JSON-lines file kept out of the repository), so 0.23.0 and 0.24.0 scan exactly
the same bytes. Only results are published.
"""
import gzip
import json
import sys
import time
from pathlib import Path

import httpx
from defusedxml import ElementTree

UA = "pagevet (page audit for text aimed at AI models; false-alarm check)"
LANGS = ["en", "es", "fr", "de", "pt", "it", "nl", "pl", "sv", "ru", "ja", "zh"]
FEEDS = {
    "en": "https://feeds.bbci.co.uk/news/rss.xml",
    "es": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "fr": "https://www.lemonde.fr/rss/une.xml",
    "de": "https://www.tagesschau.de/index~rss2.xml",
    "pt": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml",
    "it": "https://xml2.corriereobjects.it/rss/homepage.xml",
    "nl": "https://feeds.nos.nl/nosnieuwsalgemeen",
    "pl": "https://tvn24.pl/najnowsze.xml",
    "sv": "https://www.svt.se/nyheter/rss.xml",
    "ru": "https://lenta.ru/rss/news",
    "ja": "https://www3.nhk.or.jp/rss/news/cat0.xml",
    "zh": "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",
}
client = httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True)


def wikipedia(lang: str, n: int = 20) -> list[str]:
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=random&rnnamespace=0&rnlimit={n}&format=json"
    for wait in (0, 5, 15, 30):  # Wikipedia rate-limits bursts (429): wait and ask again
        time.sleep(wait)
        r = client.get(url)
        if r.status_code != 429:
            break
    r.raise_for_status()
    return [f"https://{lang}.wikipedia.org/wiki/" + p["title"].replace(" ", "_") for p in r.json()["query"]["random"]]


def rss(url: str, n: int = 12) -> list[str]:
    r = client.get(url)
    r.raise_for_status()
    root = ElementTree.fromstring(r.content)
    links = [el.text.strip() for el in root.iter("link") if el.text and el.text.strip().startswith("http")]
    return list(dict.fromkeys(links[1:]))[:n]


def build_urls(out: Path) -> None:
    rows, counts = [], {}
    for lang in LANGS:
        for name, fn in ((f"{lang}.wikipedia", lambda lang=lang: wikipedia(lang)), (f"{lang} news", lambda lang=lang: rss(FEEDS[lang]))):
            try:
                got = fn()
            except Exception as exc:  # one source failing must not lose the others
                sys.stderr.write(f"{name}: skipped: {type(exc).__name__}\n")
                got = []
            counts[name] = len(got)
            rows += [f"{lang}\t{u}" for u in got]
    out.mkdir(parents=True, exist_ok=True)
    (out / "urls.txt").write_text("\n".join(rows) + "\n")
    (out / "sources.json").write_text(json.dumps(counts, indent=1) + "\n")
    sys.stdout.write(f"{len(rows)} URLs\n")


def fetch_pages(out: Path, pages: Path) -> None:
    from pagevet.scan import Robots, fetch

    robots = Robots(lambda u: fetch(u, timeout=10.0, max_bytes=500_000))
    with gzip.open(pages, "wt") as fh:
        for line in (out / "urls.txt").read_text().splitlines():
            lang, url = line.split("\t", 1)
            row = {"lang": lang, "url": url}
            if not robots.allowed(url):
                row["error"] = "robots.txt disallows"
            else:
                try:
                    row["html"] = fetch(url, timeout=20.0, max_bytes=5_000_000)
                except Exception as exc:  # recorded, not retried another way
                    row["error"] = f"{type(exc).__name__}"
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            time.sleep(0.2)


def scan_pages(pages: Path, out: Path) -> None:
    import pagevet
    from pagevet.scan import scan_text

    rows, total = [], 0.0
    with gzip.open(pages, "rt") as fh:
        for line in fh:
            row = json.loads(line)
            if "html" not in row:
                rows.append({"lang": row["lang"], "url": row["url"], "read": False, "error": row.get("error", "")})
                continue
            t0 = time.perf_counter()
            result = scan_text(row["url"], row["html"])
            dt = time.perf_counter() - t0
            total += dt
            rows.append({"lang": row["lang"], "url": row["url"], "read": True, "seconds": round(dt, 4),
                         "findings": [{"channel": f.channel, "severity": f.severity, "kinds": f.kinds, "excerpt": f.excerpt} for f in result.findings]})
    read = [r for r in rows if r["read"]]
    by_lang = {}
    for r in read:
        s = by_lang.setdefault(r["lang"], {"read": 0, "medium_or_high": 0, "low": 0})
        s["read"] += 1
        sev = {f["severity"] for f in r["findings"]}
        s["medium_or_high"] += bool(sev & {"medium", "high"})
        s["low"] += sev == {"low"}
    summary = {"version": pagevet.__version__, "pages": len(rows), "read": len(read),
               "medium_or_high": sum(v["medium_or_high"] for v in by_lang.values()), "low_only": sum(v["low"] for v in by_lang.values()),
               "scan_seconds_total": round(total, 2), "by_language": by_lang}
    out.write_text(json.dumps({"summary": summary, "pages": rows}, indent=1, ensure_ascii=False) + "\n")
    sys.stdout.write(json.dumps(summary, indent=1) + "\n")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "urls":
        build_urls(Path(sys.argv[2]))
    elif cmd == "fetch":
        fetch_pages(Path(sys.argv[2]), Path(sys.argv[3]))
    elif cmd == "scan":
        scan_pages(Path(sys.argv[2]), Path(sys.argv[3]))
